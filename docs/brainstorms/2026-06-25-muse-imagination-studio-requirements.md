---
date: 2026-06-25
topic: muse-imagination-studio
maturity: requirements-ready
source: docs/ideation/2026-06-25-muse-ideation-comparison.md (studio synthesis) + docs/ideation/2026-06-25-muse-codex-gpt55-ideation.md (Codex second opinion) + docs/ideation/2026-06-25-muse-codex-requirements-review.md (Codex requirements-review pass) + docs/ideation/2026-06-25-muse-command-design-ideation.md (/ideate); seed docs/ideation/2026-06-24-muse-imagination-plugin-seeds.md
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
- **Thin-slice the loop; don't deep-build any one surface.** "All four surfaces" means a minimal *closed*
  version of each — enough that the loop runs end-to-end — not full-depth foraging, full adaptivity, a
  rich canvas, and the whole satellite suite at once. The v1 bar is the loop closing, not depth on any
  surface. *(Pre-mortem: four impressive demos that don't interlock, so the loop never actually closes.)*
- **Critique-ban is structural and behavioral.** A yes-and behavior contract with no evaluative
  affordance — grounded in evaluation-apprehension and self-monitor-suppression research, not a stated
  preference that erodes turn by turn.
- **The method engine's product is the "when," not the "what."** The catalogue is table stakes; the
  expertise is a selection policy that reads the session and times the move. Methods run *invisible* by
  default — felt, not narrated — and only stay hidden because rotation keeps them fresh.
- **Invisible in-session, legible after.** Methods run unannounced during play (R6), but a private
  after-action trace (R29) makes the timing legible *afterward*. Permanent opacity fights SC1 — the
  operator cannot tell expert timing from random prompt variation, and trust never compounds — so
  delayed inspectability, not total silence, is the rule. *(Pre-mortem: feels like generic chat with a
  hidden prompt library.)*
- **The canvas is the partner's rendering of the shared model, not the operator's drawing tool.** Agent
  renders from the conversation; the operator steers by pointing and words; it must be legible enough to
  *disagree with*. Direct manipulation is an escape hatch, not the default. The structured model is the
  agent's source of truth; the operator only ever sees and points at the *rendered visual*, never the
  model itself. *(Pre-mortem: a decorative SVG generator the operator debugs instead of thinking.)*
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
  canvas snapshot + quarantined doubts, the doubts typed at this airlock) and routes it to `/ideate`;
  nothing is critiqued in the assembly.
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
- R2. Doubts are quarantined, not answered — any doubt (operator's or surfaced) is captured verbatim to a
  parking lot, held unanswered and *uncategorized in-session* (categorizing a doubt is itself a faint
  evaluative act), and travels with the thread to `/ideate`; it is typed only at graduation (see R39).
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
  never dead-wired. It consumes the capture of R28 and the after-action trace of R29.
- R26. Flow-monitor inputs — the engine observes explicit signals: novelty rate, repeated node revisits,
  unresolved metaphors, canvas-correction frequency, branch breadth, stalling or silence, and
  premature-closure language. These are the concrete inputs R5's selection acts on.
- R27. Flow-state detection — the system defines detectable states (flowing / rut / stuck / too-focused /
  too-unfocused / closure-pressure), each with default moves and cooldowns, so selection cannot loop the
  same prompt shape (the R8 failure).
- R28. Learning-signal capture — each move records an *inferred* outcome (operator continues / redirects /
  rejects / screenshots / reopens / graduates / abandons / says "that moved it"); explicit ratings are
  optional and post-session only, never in-session (an in-session rating would be the evaluative act R3
  forbids). This is the producer R10 consumes.
- R29. After-action trace — at session close the partner emits a *private* trace: what moved, what
  stalled, which moves fed which seeds, and which prompts *overworked* (annoyed, shrank the field, or
  forced premature convergence — the "method diet"). Methods stay invisible in-session (R6); the trace
  makes the expertise legible afterward, fuels R10/R28, and is how the operator comes to trust the timing
  without breaking flow.

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
- R30. Canvas source model — the canonical canvas is a structured model (typed nodes, claims, tensions,
  metaphors, clusters, links, with stable IDs); the rendered visual (SVG/HTML, the `muse-studio-anatomy.png`
  grade) is produced *from* it. **The operator always works against the rendered visual and never reads or
  edits the underlying model** — the model exists so the picture stays faithful, stable across sessions,
  and precisely pointable, not as a surface the operator touches.
- R31. Canvas correction protocol — a pointing gesture, screenshot annotation, or natural-language
  correction resolves to a stable node ID or named region; a re-render preserves node identity and layout
  unless the operator explicitly splits, merges, renames, or moves something. This is what makes R12/R14's
  "this one — move it there" a precise edit rather than a full redraw.

**Durability and active incubation**

- R16. Each thread is a durable, resumable corpus the partner rehydrates fully from plain text and JSON
  across days.
- R17. Resurfacing is collision-driven — the partner resurfaces a dormant thread when new material
  collides with it and brings the concrete spark, not a generic "still itching?" nag.
- R18. The partner forages proactively across the operator's journal, diffs, and other threads (wider
  sources optional) for collisions worth resurfacing — bounded and cadence-controlled.
- R19. Soak is a feature — threads are expected to lie dormant and compound; dormancy is not abandonment.
- R32. Collision ledger — foraging records *why* a spark collided, which source triggered it, and whether
  the operator actually reopened — the producer for R17/R18 and the measurable signal behind SC3.
- R33. Re-entry ritual — reopening a thread surfaces the spark, the current visual model, the last
  unresolved metaphor, and one live invitation, so soak becomes operational re-entry, not just durable
  storage.
- R34. Foraging safety envelope — foraging defines allowed sources, a cadence, a cost cap, a maximum
  resurfacing volume, and suppression rules, so active incubation stays useful collision and never becomes
  background nagging.

**Graduation and boundary**

- R20. A thread graduates when the mental model feels complete — the completion signal assembles a bundle
  (seeds + canvas snapshot + quarantined doubts) and routes it to `/ideate`.
- R21. Quarantined doubts ride along to `/ideate` to be answered there, never in-session.
- R22. `/muse` sits upstream of `/ideate` and does not replace `/office-hours` — office-hours stays and
  `/muse` is invisible to it.
- R23. `/muse` is off-chain like `/ideate` and `/office-hours`, and keeps its own durable corpus; it does
  not write saga work-state.
- R35. Cold-start behavior — before learned data exists (session one), the partner runs a curated default
  method diet and seeded preferences and learns fast post-session, rather than feigning a personalization
  it has not earned.
- R36. Critique escape hatch — if the operator asks for a reality check inside `/muse` ("is this even
  feasible?"), the partner does not answer it in-session; it parks the request as a doubt and offers to
  graduate or fork to `/ideate`. The ban has a release valve so it never feels like a straitjacket.
- R37. Completion heuristic — graduation stays operator-authoritative (R20); the partner may only
  *suggest* readiness when the canvas stabilizes, unresolved primitives decline, language stops changing,
  and doubts are sufficiently captured — a suggestion, never a forced convergence.
- R39. Doubt typing at the airlock — at graduation (F3) the parked doubts are typed (feasibility / ethics
  / taste / implementation / contradiction / operator-discomfort) so they route well into `/ideate`. The
  typing happens *only* here, at the exit — never in-session (R2), where it would be a faint evaluative
  act.

**Third-party satellites**

- R24. Satellites round-trip manually in v1 — the partner exports a source pack, the operator works in a
  real creative app (NotebookLM, Gemini Canvas, MindNode, Excalidraw, Google Docs), and imports the
  output back to be distilled into the spine.
- R25. The plain-text and JSON spine is the only source of truth — satellites enrich but never become
  load-bearing, and deep unofficial-API automation is a later spike.
- R38. Satellite provenance — every import (NotebookLM, Gemini, MindNode, Excalidraw, Docs) returns
  wrapped with source, date, an operator note, and "what it changed in the thread," so satellites stay
  useful (R24) without becoming authoritative (R25).

## Acceptance Examples

Conditional behaviors where prose alone leaves edge-case ambiguity.

- AE1. **Covers R5, R8, R26, R27.** **Trigger:** three turns circle the same node with no new material
  (low novelty rate + repeated revisits → the "rut" state). **Behavior:** the partner switches to a
  deliberately unrelated stimulus rather than another similar prompt, respects the cooldown so it does not
  re-fire the same move, and does not announce the method.
- AE2. **Covers R12, R13, R30, R31.** **Trigger:** the operator screenshots a cluster and says "heartbeat
  isn't about presence — it's its own thing." **Behavior:** the partner resolves the gesture to that
  node's stable ID, re-renders moving *only* that node (every other node keeps its identity and place),
  and treats the correction as signal about the shared model, not a cosmetic edit.
- AE3. **Covers R17, R18, R32.** **Trigger:** a new journal entry or diff rhymes with a dormant thread.
  **Behavior:** the partner resurfaces that thread with the concrete spark ("this new X connects to your
  dormant Y"), records the collision (source + why) to the ledger, and does not send a timer-driven nag.
- AE4. **Covers R20, R21, R39.** **Trigger:** the operator says the model feels complete. **Behavior:**
  the partner assembles seeds + canvas snapshot + parking-lot doubts into a bundle, types the doubts at
  this airlock, and offers routing to `/ideate`; nothing in the assembly is critiqued.
- AE5. **Covers R6, R7.** **Trigger:** the operator asks "what are you doing?" mid-session. **Behavior:**
  the partner names the current move and why it chose it, then continues; absent the question, it never
  labels the technique.
- AE6. **Covers R36.** **Trigger:** mid-session the operator asks "wait — is this actually buildable?"
  **Behavior:** the partner does not answer the feasibility question in-session; it parks it as a doubt
  and offers to graduate or fork to `/ideate`. No evaluation leaks back into the room.
- AE7. **Covers R29, R28.** **Trigger:** a session ends. **Behavior:** the partner emits a private
  after-action trace (what moved, what stalled, which moves fed which seeds, which overworked) and records
  the inferred outcome signals — none of it shown or discussed in-session.

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
- SC6. The expertise is legible after the fact — the after-action trace (R29) lets the operator see *why*
  it felt expert (which moves landed when), so timing stops reading as luck and trust compounds. This is
  the measurable resolution of "invisible in-session" not fighting SC1.

## Scope Boundaries

**Deferred for later (eventually, not v1)**

- Full-depth on any single surface — v1 builds minimal *closed* versions of all four (thin-slice the
  loop). Deep foraging, full adaptivity, rich canvas interaction, and the complete satellite suite are
  post-v1; the new mechanics (R26–R39) are specified for v1 but built to the minimal-closed bar, not to
  depth.
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
  `plugins/saga/docs/assets/` is the working precedent for the *render*, and the typed source model (R30)
  plus the exact render format are `/plan`'s call.
- The learning leg assumes enough repeated sessions accrue to make adaptation meaningful — sparse data
  early is expected, not a failure; R35 (cold-start) covers the pre-data sessions.
- Foraging assumes a bounded cost and cadence envelope (R34); unbounded background agency is a non-goal.
- Durability assumption: the value rests on the operator returning across days. If real usage is
  one-and-done, the compounding-thread and learning legs underdeliver — mitigated by collision-driven
  resurfacing (R17) and the re-entry ritual (R33) but not eliminated.
- No-dead-wiring invariant: every captured signal has a live consumer — learning capture (R28) → R10,
  collision ledger (R32) → R17/SC3, flow-monitor inputs (R26) → R5/R27, after-action trace (R29) → R10.
  `/plan` must not add a producer without a named reader.

## Outstanding Questions

**Resolve before planning**

- **Corpus layout — committed vs. machine-local.** A thread needs a durable, git-diffable home (the
  plain-text-spine durability bet). Open sub-question: committed under `docs/muse/<thread>/` (per the seed
  doc — portable, diffable, journal-visible) vs. a gitignored machine-local corpus (private, but
  non-portable and undercuts the diffable-spine bet). **Lean: committed `docs/muse/`.** Note "off-chain"
  means no saga *work-state*, not "gitignored." This is the one item genuinely unsettled by stated
  preference, so it resolves at the top of `/plan`.

**Planning defaults (proposed, operator-aligned — `/plan` inherits unless it finds reason to diverge)**

- **Canvas render format + pointing map.** Canonical canvas is the structured model (R30); rendered output
  is SVG first, HTML optional later. Pointing resolves through stable node IDs, visible labels, screenshot
  annotation, or natural-language references to named clusters (R31). v1 runtime surface: generate
  SVG/HTML files from the corpus and open them in the browser/viewer — *not* a full canvas editor.
- **Which satellites first + import formats.** A generic source pack plus manual imports for NotebookLM,
  Gemini Canvas, MindNode, Excalidraw, and Google Docs (Markdown / JSON / OPML / Excalidraw-JSON / pasted
  text), each wrapped with provenance (R38).
- **Foraging cadence + sensitivity + cost.** Local-source foraging on session close and on a bounded daily
  cadence; precision over recall; a small spark queue; no nag without a concrete collision (R34). v1
  privacy: local journal, diffs, and existing muse threads only — wider web/app integration later, after
  the collision ledger proves value.
- **Completion detection.** Operator declaration is authoritative; the partner may only suggest readiness
  on stabilization signals (R37).
- **Method→outcome learning capture.** Inferred by default, optional post-session ratings, never
  in-session (R28).
- **Dangerous / risky material.** Still no in-session critique; park the risk as a quarantined doubt and
  recommend immediate graduation or fork to `/ideate` when the operator explicitly asks for judgment (R36).

## Sources / Research

- `docs/ideation/2026-06-24-muse-imagination-plugin-seeds.md` — the 28-seed imagination doc.
- `docs/ideation/2026-06-25-muse-command-design-ideation.md` (/ideate), `…-muse-codex-gpt55-ideation.md`
  (Codex gpt-5.5 second opinion), `…-muse-ideation-comparison.md` (the studio synthesis + visuals).
- `docs/ideation/2026-06-25-muse-codex-requirements-review.md` — Codex gpt-5.5 (xhigh)
  requirements-review pass against this doc (verdict: plan-ready-with-fixes); source of the R26–R39
  mechanics, the thin-slice principle, and the planning defaults above.
- `docs/ideation/assets/` — studio anatomy and session storyboard visuals.
- `DECISIONS.md` {#saga-docs-source-model} — pro-visual; the model→SVG kit is the canvas precedent the
  earlier "text-only" cut overlooked.
- `LEARNINGS.md` {#ideate-on-imagination-doc-imports-constraints} (why this brainstorm bypassed the
  convergent engine's framing); {#dead-wiring-needs-producer-and-consumer} (the producer-first learning
  seam in R10).
- External grounding: Diehl & Stroebe 1987 (evaluation apprehension); Limb & Braun 2008 (DLPFC
  suppression); Wallas incubation; Campbell 1960 / Simonton 2011 BVSR (blind variation → R5's deliberate
  randomness).
