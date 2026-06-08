---
name: plan
description: Create durable Infiquetra implementation plans with issue, review, test, and deploy gates. Interrogates HOW work gets built, writes an agent-consumable plan artifact, records a plan saga, and routes to doc-review and /work. Triggers on "plan this", "how should we build this", "create a plan", "break this down", or a handoff issue ready for planning.
---

# Plan

`/plan` answers **"How should it be built?"** It takes a settled WHAT — from `/brainstorm`'s
requirements doc, a handoff issue, or a clear ad-hoc request — and interrogates it into a durable,
agent-consumable implementation plan. It does **not** invent product behavior (that came from
`/brainstorm` or the issue), it does **not** implement code, and it does **not** run the review
gauntlet. It plans, self-reviews, records a plan saga, and routes.

## Position in the lifecycle

`/plan` sits between requirements and execution:

- `/office-hours` answers: "What is even the right frame?"
- `/ideate` answers: "What are the strongest ideas worth exploring?"
- `/brainstorm` answers: "What exactly should one chosen idea mean?" (the WHAT)
- **`/plan` answers: "How should it be built?"** (the HOW — this engine)
- the `review` phase (`/doc-review`) answers: "Is this plan ready to execute?"
- `/work` answers: "Build it." (consumes the plan + saga)

The handshake is deliberate. When the WHAT is unsettled, `/plan` recommends the operator step back to
`/brainstorm` first (a one-way forward route — `/plan` points there; it does not claim `/brainstorm`
"accepts" a handoff). When the plan is written, `/plan` recommends `/doc-review` (the review phase)
before `/work`.

## Core principles

1. **Decisions, not code.** Capture approach, boundaries, files, dependencies, risks, and per-unit
   test scenarios. Do not pre-write implementation code or shell-command choreography. Pseudo-code and
   DSL grammars are allowed only as explicitly directional high-level design, never as implementation
   specification.
2. **Ground before asking.** Read the code before you ask a question its answer is already in. Cite
   `path:line`. Quantify everything — "several files" is a bug; find the exact count. Never guess about
   the codebase; go read it.
3. **Agent-consumable plans.** The plan must let an unfamiliar implementer (human or `/work`) start
   confidently without re-asking the operator. Stable IDs (R-IDs, KTDs, U-IDs), per-unit test
   scenarios with repo-relative test-file paths, dependency-ordered units.
4. **Right-size via the warranted-gate.** Not every invocation produces a plan doc. Genuinely atomic
   work skips the artifact. But stress-test the "looks atomic" case — most requests hide KTDs.
5. **HOW-only.** Assume the WHAT arrived from `/brainstorm` or the issue. Do not re-litigate product
   scope, actors, or success criteria here — carry them forward as constraints.

## Interaction method

Use `AskUserQuestion` for choices from a known set (destination, execution backend, scope class,
resume-vs-mint). Call `ToolSearch` with `select:AskUserQuestion` first if its schema is not loaded.
Ask one question per turn; prefer a concise single-select when natural options exist. For open-ended
interrogation, ask inline in chat. Never silently skip a question.

In a channel session (`redis-channel` active), `AskUserQuestion` cannot be called — inline the choices
in your reply text instead. Follow the canonical channel-inline convention in
`saga/skills/brainstorm/SKILL.md` (do not duplicate its wording here).

Use repo-relative paths in every generated document. Absolute paths break portability across machines
and worktrees.

---

## Phase 0 — Enter and warranted-gate

Capture the input and decide whether a plan doc is even warranted before spending interrogation effort.

### 0.1 Capture input

The input is an issue reference, a requirements doc path, or an ad-hoc request. Take it from command
arguments or the active artifact. If empty, ask: "What would you like to plan? Point me at the
requirements doc, the issue, or describe the work." Do not proceed without one.

### 0.2 Issue handoff routing

If the input is a GitHub issue, run `scripts/parse_issue.py` and inspect the `handoff` object.

- For `idea-ready` or `requirements-ready` handoff issues, create or update a durable plan from the
  issue and its `Source context` / linked source. These are the maturities `/plan` consumes.
- For `plan-ready` or `resume-ready` handoff issues, tell the operator `/work <issue>` is the more
  direct consumer unless they explicitly want to re-plan. A plan already exists for these.

Use the issue's `Handoff maturity` and `Source context` sections as authoritative input.

### 0.3 Saga scan — offer resume before minting

Before minting a new plan saga, run `scan` to offer resuming an existing one (slug-instability
mitigation — a drifting task description would otherwise fork a second saga for the same work):

```bash
python3 plugins/saga/scripts/saga.py scan
```

If a candidate matches this thread (same `issue_ref`, or the operator confirms "resume this"), reuse
it — Phase 5 appends a tick rather than minting. For an issue whose `issue-<N>` directory is absent,
resolve via `state.json.sagas[*].issue_ref` ending in `#N` (the id is sticky; never rename the
directory). See `references/saga-spec.md` §2.3 and §2.1.

### 0.4 Warranted-gate — decide whether a plan doc is warranted

Bias toward producing a plan; the risk asymmetry favors writing one. **Skip the plan doc only when ALL
hold:** the work is atomic (fits one commit, no unit boundaries), there are no Key Technical Decisions
worth recording, no scope boundaries worth pinning, and no upstream artifact needs traceability.

**Stress-test the "looks atomic" case** — many requests look atomic but hide KTDs ("add caching" →
TTL / invalidation / key shape; "migrate A to B" → semantic-difference KTDs; "add rate limiting" →
algorithm / scope / configurability). See `references/plan-sections.md` ("Decide whether a plan doc is
warranted") for the full skip-vs-write rubric. When skipping, route directly to `/work` and let
decisions land in the commit message; otherwise continue.

### 0.5 Scope classification

Classify the work into one depth, which sizes the plan (Phase 3) and gates the deepening pass (Phase 4):

- **Lightweight** — small, well-bounded, low ambiguity. ~2-4 units. Omit optional sections.
- **Standard** — normal feature or bounded refactor with technical decisions to document. ~3-6 units.
- **Deep** — cross-cutting, strategic, high-risk, or highly ambiguous. ~4-8 units; optional analysis
  sections warranted.

If depth is unclear, ask one targeted question, then continue.

---

## Phase 1 — Ground (HOW)

Read code before asking. This is the moment the operator sees you grounded in their actual repo, not a
generic checklist.

1. **Read the upstream artifact first.** If a `/brainstorm` requirements doc (`docs/brainstorms/*-requirements.md`),
   the handoff issue, or a linked source exists, read it thoroughly and carry forward its problem frame,
   requirements, scope boundaries, KTDs, and open questions as constraints the plan must honor.
2. **Read `STRATEGY.md`** if present and anchor plan decisions to the active tracks; flag any decision
   that pulls away from the stated approach.
3. **Read the engineering journal** (`docs/engineering-journal/`) for relevant prior LEARNINGS and
   DECISIONS so the plan follows established patterns instead of reinventing them.
4. **Quantify.** Find exact counts (files, call sites, tables). Cite `path:line` in your prose.
5. **Dispatch generic `Explore` agents in parallel** for grounding — repo patterns, relevant files,
   existing test conventions, adjacent implementations. Use the generic `Explore` agent; the `ce-*`
   research agents do **not** exist in this plugin.

**Cold-start (no upstream WHAT).** If there is no brainstorm doc, no issue, and the request is bare:
run a light Why-check (problem frame, intended behavior, obvious non-goals, success signal — keep it
brief; see `references/interrogation.md`). If the WHAT itself is unsettled — product framing, user
behavior, or scope is genuinely open — **recommend the operator run `/brainstorm` first** to settle
the WHAT, then return to `/plan`. This is a one-way forward route: point them there, offer to continue
planning with explicit assumptions if they decline, and do not claim `/brainstorm` "accepts" a handoff.

---

## Phase 2 — Interrogate (HOW)

**Load `references/interrogation.md`** and run the HOW-interrogation register against the grounded
evidence. Ambiguity is a bug; find it. The register covers:

- **Failure-mode enumeration** — for each unit, what happens when the input is empty, null, huge,
  duplicated, called by the wrong role, or called twice. Unenumerated failure modes are unwritten test
  scenarios.
- **Scope-lock** — lock what is explicitly out of scope early. When the operator opens a new front
  mid-plan, name it: "That's a separate issue — let's finish this one."
- **KTD-forcing** — surface the load-bearing technical decisions and force a choice with rationale.
  An open design fork the plan never resolves is a gap, not a decision.
- **Anti-premature-solution** — do not jump to implementation detail before the approach, boundaries,
  and failure modes are pinned.

Push on **vagueness** and **ungrounded assumptions** (not the operator's judgment): an undefined term,
a "several files" that should be a count, a behavioral assumption you have not verified in the code.
Push twice, then respect the answer. Escape hatches are in `references/interrogation.md`.

---

## Phase 3 — Synthesize the plan artifact

Write the plan to `docs/plans/YYYY-MM-DD-<topic>-plan.md` per `references/plan-sections.md`. Right-size
by the Phase-0.5 scope class. **Never code during this phase** — research, decide, and write the plan.

Follow the shared formatting contract in `saga/references/formatting-style.md` for the plan's visual
structure: lead each unit and major section with a one-line summary, keep narrative fields as short
(≤3-sentence) blank-line-separated prose, render comparative/scored data as a table, and never stack
bold labels without a blank line between them. Per-unit fields stay as blank-line-separated
`**label:**` lines under each `### U<N>.` heading (the contract's prose-heavy per-unit branch) — not a
table.

**Hard floor (every warranted plan carries these):**

- **Summary** — what the plan proposes, in 1-3 lines.
- **Problem Frame** — why the work is being done (may merge into Summary for compact plans).
- **Requirements** — with stable **R-IDs** (`R1.`, `R2.`); the reviewer's and `/work`'s checklist.
- **Key Technical Decisions** — the **KTDs**, each `<decision>: <rationale>`; the load-bearing choices
  that constrain implementation.
- **Implementation Units** — with stable **U-IDs** (`U1.`, `U2.`), each independently landable, with
  per-unit test scenarios and repo-relative test-file paths. Feature-bearing units require real test
  scenarios; only non-feature units (config, scaffolding) may use `Test expectation: none -- [reason]`.
- **Scope Boundaries** — what is explicitly out of scope, with `Deferred to Follow-Up Work` kept
  distinct from true non-goals.

**Deep adds (warranted only, never boilerplate):** High-Level Technical Design (HTD), Risk Analysis &
Mitigation, Alternatives Considered, Success Metrics. Include only when the content earns the section.

The plan must serve **three audiences**: the implementing agent (informed starting baseline), the
reviewer (load-bearing decisions in one pass), the future reader (why the work was done).

**Plan-doc frontmatter** (NOT the saga fields — those land in Phase 5):

```yaml
---
title: <verbatim plan title, matches the H1>
type: <feat|fix|refactor|chore|docs|perf|test>
status: active
date: YYYY-MM-DD
origin: <repo-relative path to the upstream brainstorm/requirements doc, when planning from one>
---
```

`origin:` MUST be emitted so the review phase can trace the plan back to its source. The body MUST use
the exact section markers `Implementation Units`, `Key Technical Decisions`, and the `U1` U-ID prefix —
`/doc-review` parses these to recognize the document as a plan.

**Record the KTDs to the engineering journal** (`docs/engineering-journal/DECISIONS.md`) — the journal
is the canonical decision record; the saga's `## Decisions` mirrors it.

---

## Phase 4 — Deepen (condensed confidence pass, conditional)

After writing the plan, evaluate whether it needs strengthening. The condensed confidence-pass rubric
lives in the **Confidence pass (deepening)** section of `references/plan-sections.md` — per-section gap
checklist, risk-weighted "is this plan thin?" scoring, and the top-N section cap.

- **Auto-run** for Deep plans, high-risk topics (auth, payments, data migration, external APIs,
  privacy), or thin grounding (Phase 1 found fewer than ~3 local patterns for what the plan needs).
- **Skip** for Lightweight, well-grounded plans — report "Confidence check passed" and continue.

When deepening, dispatch generic `Explore` / `Task` agents (not `ce-*` agents) at the top-scoring
sections only. Strengthen rationale, sequencing, test scenarios, and risk treatment in place. **Never
renumber existing U-IDs** when reordering or splitting units (the most likely accidental-renumber
vector). Add `deepened: YYYY-MM-DD` to frontmatter when the plan was substantively improved.

---

## Phase 5 — Saga, route, and operator-choice

### 5.1 Ask the destination

Ask the routing intent (`AskUserQuestion`, or channel-inline): **plan-only / pr / merge /
nonprod-deploy**. This becomes the saga `--destination`.

### 5.2 Offer the execution backend

Offer the execution backend per `references/operator-choice.md` (the decision contract). There are
exactly three backends — `inline | team-execution | cc-workflows-ultracode`. Read the work shape,
**recommend the cheapest-correct** backend and pre-select it, but always surface the alternatives so
escalation is one step. Escalate to `team-execution` for risky/consensus work (≥8 files, ≥4 phases,
security, infra, cross-repo, deployment-sensitive, plus a needs-consensus signal); to
`cc-workflows-ultracode` for broad independent fan-out without elevated risk. Omit
`cc-workflows-ultracode` from the offer when the Workflow tool is observably absent in this session.
Confirm with the operator and record what they picked via `--orchestration-mode`.

### 5.3 Write the saga tick

Emit a **runnable** saga `save` command — never prose like "write a saga", and never `git add` the
tick (saga state is git-ignored, machine-local). Use the real flags:

```bash
python3 plugins/saga/scripts/saga.py save \
  --kind <issue|task> \
  --id <issue-number-or-task-slug> \
  --lifecycle-phase plan \
  --plan-path docs/plans/YYYY-MM-DD-<topic>-plan.md \
  --destination <plan-only|pr|merge|nonprod-deploy> \
  --adr-refs "ADR-NNNN|ADR-MMMM" \
  --decisions "KTD1: rationale. KTD2: rationale." \
  --orchestration-mode <inline|team-execution|cc-workflows-ultracode>
```

`--id` is the only strictly required flag (`--kind` defaults to `issue`); for ad-hoc work pass
`--kind task --id <slug>`. `--lifecycle-phase plan`, `--plan-path`, `--destination`, `--adr-refs`,
`--decisions` (the KTD mirror), and `--orchestration-mode` carry the `/plan` consumer row from
`references/saga-spec.md` §11. When resuming (Phase 0.3 matched), this appends a tick to the existing
saga directory rather than minting a new one.

### 5.4 Route

Recommend the next command with plural clean exits:

- **`/doc-review`** (recommended next) — the review phase. `/work` gates on doc-review and blocks on
  unresolved P0/P1 findings, so run the review before execution.
- **`/work`** — execute the plan (after doc-review).
- **`/handoff`** — hand the plan to an SDLC issue through `mission-control`.
- **`/brainstorm`** — step back if interrogation revealed the WHAT was not actually settled.

### 5.5 Hard boundary

`/plan` authors a plan artifact and self-reviews it. It does **NOT** implement code, does **NOT** file
SDLC issues (`mission-control` owns issue creation), and does **NOT** run the full review gauntlet
(`/doc-review` owns that). Plan, write the saga, route — then stop.
