---
date: 2026-06-25
topic: muse-imagination-studio
maturity: requirements-ready
source: docs/ideation/2026-06-25-muse-ideation-comparison.md (studio synthesis) + docs/ideation/2026-06-25-muse-codex-gpt55-ideation.md (Codex second opinion) + docs/ideation/2026-06-25-muse-command-design-ideation.md (/ideate); seed docs/ideation/2026-06-24-muse-imagination-plugin-seeds.md
---

# Brainstorm: /muse — the imagination studio

## Summary

`/muse` is a critique-banned, multi-session imagination studio: one integrated loop where an invisible
expert method engine drives divergence, an agent-rendered visual canvas externalizes the shared model,
doubts are quarantined, and threads compound across days until a mental model feels complete and
graduates to `/ideate`.

## Problem Frame

The saga fuzzy front end has no room where ungrounded, half-formed ideas are safe. `/ideate`'s defining
rule cuts any idea with no articulated basis — exactly what kills "throw it at the wall, I can't justify
it yet." The blank page and the reflexive inner critic ("is this good enough to write down?") finish the
job, and a fragile idea dies before it can mutate into something worth grounding.

Running the `/muse` seed doc through `/ideate` itself proved the gap: the convergent engine cut the
visual surface, deferred third-party creative apps, and demoted the method library — reproducing on
`/muse`'s own design the very limitation `/muse` exists to escape. The need is a place upstream of
`/ideate` where critique and convergence are structurally absent.

## Product Thesis

The bet is that an imagination partner which is an *expert at creative method* (knowing WHEN to apply
which move), *adapts to the individual* over time, and *forages on their behalf* between sessions is
categorically different from a clever unrestricted chat.

The four surfaces — critique-banned room, expert method engine, agent-rendered canvas, compounding
multi-session thread — are one integrated loop; none delivers the value alone. The differentiator is not
"critique off"; it is the closed loop that keeps fragile, unjustifiable material alive and mutating until
it is solid enough to hand to `/ideate`. A static, in-session-only tool would not prove this bet, so the
adaptivity and the foraging are in v1, not deferred.

## Key Decisions

Opinionated framing choices that constrain the requirements below.

- **Integrated loop, not a feature menu.** v1 is "make the loop close," not "ship the highest-value
  surface." All four surfaces are load-bearing; the value is their interplay.
- **Critique-ban is structural and behavioral.** A yes-and behavior contract with no evaluative
  affordance — grounded in evaluation-apprehension and self-monitor-suppression research, not a stated
  preference that erodes turn by turn.
- **The method engine's product is the "when," not the "what."** The catalogue is table stakes; the
  expertise is a selection policy that reads the session and times the move. Methods run *invisible* by
  default — felt, not narrated — and only stay hidden because rotation keeps them fresh.
- **The canvas is the partner's rendering of the shared model, not the operator's drawing tool.** Agent
  renders from the conversation; the operator steers by pointing and words; it must be legible enough to
  *disagree with*. Direct manipulation is an escape hatch, not the default.
- **Incubation is active and collision-driven, not a calendar nag.** The partner forages for new
  material that collides with dormant threads and resurfaces them *with the spark*.
- **Per-you learning is a designed-in seam, shipped as producer-first.** v1 tags the method→outcome
  signal so the adaptive selection has fuel; the consumer deepens over time. The seam is built
  deliberately to avoid the dead-wiring failure mode (a reader with no producer, or a producer with no
  reader).
- **Graduate on "the model feels complete."** Completion is the exit signal; it assembles a bundle and
  routes to `/ideate`, where critique and the parked doubts get answered.
- **Don't replace `/office-hours`; sit upstream of `/ideate`.** `/muse` is off-chain and keeps its own
  durable corpus; it does not touch the office-hours surface (hardcoded in tests + a routing target).

## Actors

- A1. **Operator** — a single person, engineering topics first, thinking out loud; needs to see and
  point at the shared model.
- A2. **Muse partner (in-session)** — dual provocateur + scribe; runs the invisible expert method engine
  and renders the canvas.
- A3. **Foraging agent (between sessions)** — bounded background agency that hunts for collisions and
  resurfaces dormant threads with a concrete spark.
- A4. **`/ideate` (downstream)** — the convergent consumer that grounds and filters a graduated bundle;
  where critique and the quarantined doubts are finally answered.

## Key Flows

- F1. **A session.** Trigger: the operator opens `/muse` with an itch, or re-enters a resurfaced thread.
  The partner elicits (inchoate metaphor work), runs invisible method moves to fan out, renders the
  canvas from the talk, captures seeds silently, and quarantines doubts. Ends when the operator stops or
  the model feels complete.
- F2. **Resurfacing (collision-driven).** Trigger: the foraging agent finds new material that collides
  with a dormant thread. It resurfaces the thread *with* the concrete spark; the operator re-enters on
  that collision rather than on a timer.
- F3. **Graduation.** Trigger: the mental model feels complete. The partner assembles a bundle (seeds +
  canvas snapshot + quarantined doubts) and routes it to `/ideate`; nothing is critiqued in the assembly.
- F4. **Canvas steering.** Trigger: the render is off. The operator points or screenshots and says why;
  the partner re-renders and treats the correction as signal about the shared model. Escape hatch: a
  direct node move when words stall.
- F5. **Method loop (internal, continuous).** The flow-monitor reads session texture (flowing / rut /
  too-focused / too-unfocused / stuck) and picks the next move (advance / break / deliberate-random /
  focus / unfocus), invisibly, tagging ancestry and an outcome signal.

## Requirements

What must be true of `/muse`. IDs are stable and continuous across groups.

**The critique-banned room**

- R1. The partner runs a yes-and behavior contract — it builds, mirrors, and mutates, and never
  evaluates, questions feasibility, or raises a downside inside a session.
- R2. Doubts are quarantined, not answered — any doubt (operator's or surfaced) is captured to a parking
  lot, held unanswered, and travels with the thread to `/ideate`.
- R3. No scoring, ranking, voting, or selection affordance exists inside a session — convergence lives
  only at the exit and downstream.

**The method engine (the expert)**

- R4. The partner carries a substantive, curated method catalogue (the divergent / reframing /
  provocation / combination / perspective / future / visual families plus the inchoate-elicitation set),
  not a token list.
- R5. Method selection is the product — a flow-monitor reads session texture and chooses the move:
  advance when flowing, break a rut, inject deliberate randomness when stuck, tighten to focus or scatter
  to unfocus.
- R6. Methods are invisible by default — the partner performs the move without naming it and never
  announces the technique unless asked.
- R7. Methods are inspectable on demand and overridable — the operator can ask "what are you doing?" (it
  reveals the move and why) and can direct the engine ("hit it with SCAMPER," "100 variants").
- R8. Selection resists staleness — rotation and cooldown prevent the partner from defaulting to the same
  prompt shape, the failure that turns invisible methods into generic chat.
- R9. Every seed and move carries method ancestry internally for provenance and for the learning seam —
  not shown unless inspected.
- R10. Per-you learning is wired producer-first — the engine tags a method→outcome signal (which move
  preceded a breakthrough, which fell flat) from day one and biases future selection toward what works
  for this operator; the tagging ships even though the adaptive consumer deepens over time, so the seam is
  never dead-wired.

**The visual canvas**

- R11. The canvas is agent-rendered from the conversation by default — the operator does not start at a
  blank editable surface; the partner draws the shared model from the talk-it-out.
- R12. The operator steers the canvas by pointing or screenshotting plus natural language ("this here is
  off, and why"), and the partner re-renders.
- R13. The render must be legible enough to disagree with — specific named nodes, clusters, and links,
  because pointing-to-disagree is how the operator and partner detect they are out of sync.
- R14. Direct manipulation is an escape hatch, not the default — when verbal steering stalls, the
  operator can move a node to show intent; this is a lightweight, secondary capability.
- R15. The canvas is divergence-shaped — scatter, cluster, and link, never rank-to-decide (layout used to
  decide is convergence and belongs downstream).

**Durability and active incubation**

- R16. Each thread is a durable, resumable corpus the partner rehydrates fully from plain text and JSON
  across days.
- R17. Resurfacing is collision-driven — the partner resurfaces a dormant thread when new material
  collides with it and brings the concrete spark, not a generic "still itching?" nag.
- R18. The partner forages proactively across the operator's journal, diffs, and other threads (wider
  sources optional) for collisions worth resurfacing — bounded and cadence-controlled.
- R19. Soak is a feature — threads are expected to lie dormant and compound; dormancy is not abandonment.

**Graduation and boundary**

- R20. A thread graduates when the mental model feels complete — the completion signal assembles a bundle
  (seeds + canvas snapshot + quarantined doubts) and routes it to `/ideate`.
- R21. Quarantined doubts ride along to `/ideate` to be answered there, never in-session.
- R22. `/muse` sits upstream of `/ideate` and does not replace `/office-hours` — office-hours stays and
  `/muse` is invisible to it.
- R23. `/muse` is off-chain like `/ideate` and `/office-hours`, and keeps its own durable corpus; it does
  not write saga work-state.

**Third-party satellites**

- R24. Satellites round-trip manually in v1 — the partner exports a source pack, the operator works in a
  real creative app (NotebookLM, Gemini Canvas, MindNode, Excalidraw, Google Docs), and imports the
  output back to be distilled into the spine.
- R25. The plain-text and JSON spine is the only source of truth — satellites enrich but never become
  load-bearing, and deep unofficial-API automation is a later spike.

## Acceptance Examples

Conditional behaviors where prose alone leaves edge-case ambiguity.

- AE1. **Covers R5, R8.** **Trigger:** three turns circle the same node with no new material. **Behavior:**
  the partner switches to a deliberately unrelated stimulus rather than another similar prompt, and does
  not announce the method.
- AE2. **Covers R12, R13.** **Trigger:** the operator screenshots a cluster and says "heartbeat isn't
  about presence — it's its own thing." **Behavior:** the partner re-renders moving the node and treats
  the correction as signal about the shared model, not a cosmetic edit.
- AE3. **Covers R17, R18.** **Trigger:** a new journal entry or diff rhymes with a dormant thread.
  **Behavior:** the partner resurfaces that thread with the concrete spark ("this new X connects to your
  dormant Y"), not a timer-driven nag.
- AE4. **Covers R20, R21.** **Trigger:** the operator says the model feels complete. **Behavior:** the
  partner assembles seeds + canvas snapshot + parking-lot doubts into a bundle and offers routing to
  `/ideate`; nothing in the assembly is critiqued.
- AE5. **Covers R6, R7.** **Trigger:** the operator asks "what are you doing?" mid-session. **Behavior:**
  the partner names the current move and why it chose it, then continues; absent the question, it never
  labels the technique.

## Success Criteria

Quality and handoff signals the requirements do not already carry.

- SC1. Feels like an expert, not generic chat — provocations are varied and well-timed; the operator
  cannot predict the next prompt's shape.
- SC2. The canvas is pointable and disagree-able — the operator can put a finger on a specific wrong node
  within seconds.
- SC3. The operator actually returns — threads get re-opened across days, so the compounding-thread leg
  works in practice, not just in theory.
- SC4. Handoff is clean — a graduated bundle enters `/ideate` and survives its basis-cut without being
  clear-cut, proving the airlock attached enough basis.
- SC5. Critique never leaks — across a full session, zero evaluative, feasibility, or downside moves from
  the partner.

## Scope Boundaries

**Deferred for later (eventually, not v1)**

- Direct-manipulation canvas as a primary editing mode — escape hatch only in v1.
- Deep unofficial-API automation of NotebookLM and other satellites — manual round-trip only.
- Voice / stream-of-consciousness capture.
- A visible "it has learned you" demonstration — the learning machinery ships, but the demonstrable
  payoff needs accrued data.
- Wider-web foraging, if the journal and repo corpus prove sufficient first.

**Outside this product's identity**

- Critique, convergence, ranking, or selection — that is `/ideate`; `/muse` must never grow them.
- Replacing `/office-hours`.
- A general-purpose non-engineering creative substrate — prove on engineering topics first.
- Becoming a standalone PKM, notes, or diagram app — the spine is a means, not the product.

## Dependencies / Assumptions

- Assumes the saga off-chain Think-command pattern and journal-read access (journal-as-fuel) — both
  established in the repo.
- The canvas assumes an agent-authorable visual format kept in git; the model→SVG kit under
  `plugins/saga/docs/assets/` is the working precedent, and the exact format is `/plan`'s call.
- The learning leg assumes enough repeated sessions accrue to make adaptation meaningful — sparse data
  early is expected, not a failure.
- Foraging assumes a bounded cost and cadence envelope; unbounded background agency is a non-goal.
- Durability assumption: the value rests on the operator returning across days. If real usage is
  one-and-done, the compounding-thread and learning legs underdeliver — mitigated by collision-driven
  resurfacing but not eliminated.

## Outstanding Questions

**Resolve before planning**

- None — product behavior is decided. The items below are answerable during planning or codebase
  exploration.

**Deferred to planning**

- Corpus layout and on/off-chain persistence shape — where threads live, how seeds are addressed.
- Canvas render format, and how a screenshot or pointing gesture maps to a re-render.
- Which satellites ship first and their import formats.
- Foraging cadence, trigger sensitivity, and cost envelope.
- How "the model feels complete" is detected versus operator-declared.
- How the method→outcome learning signal is captured — operator-rated versus partner-inferred.

## Sources / Research

- `docs/ideation/2026-06-24-muse-imagination-plugin-seeds.md` — the 28-seed imagination doc.
- `docs/ideation/2026-06-25-muse-command-design-ideation.md` (/ideate), `…-muse-codex-gpt55-ideation.md`
  (Codex gpt-5.5 second opinion), `…-muse-ideation-comparison.md` (the studio synthesis + visuals).
- `docs/ideation/assets/` — studio anatomy and session storyboard visuals.
- `DECISIONS.md` {#saga-docs-source-model} — pro-visual; the model→SVG kit is the canvas precedent the
  earlier "text-only" cut overlooked.
- `LEARNINGS.md` {#ideate-on-imagination-doc-imports-constraints} (why this brainstorm bypassed the
  convergent engine's framing); {#dead-wiring-needs-producer-and-consumer} (the producer-first learning
  seam in R10).
- External grounding: Diehl & Stroebe 1987 (evaluation apprehension); Limb & Braun 2008 (DLPFC
  suppression); Wallas incubation; Campbell 1960 / Simonton 2011 BVSR (blind variation → R5's deliberate
  randomness).
