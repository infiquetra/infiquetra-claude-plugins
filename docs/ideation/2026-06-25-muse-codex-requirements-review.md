---
date: 2026-06-25
topic: muse-imagination-studio
kind: second-opinion-review
engine: codex gpt-5.5 (model_reasoning_effort=xhigh, read-only)
reviewed: docs/brainstorms/2026-06-25-muse-imagination-studio-requirements.md
verdict: plan-ready-with-fixes
disposition: operator accepted all enrichments — folded into the requirements doc (R26–R39, thin-slice principle, planning defaults) on 2026-06-25
---

# /muse requirements — Codex second-opinion review

A second, independent Codex pass — this time a **review of the requirements doc**, not a fresh
ideation (the first Codex pass was the gpt-5.5 ideation in `…-muse-codex-gpt55-ideation.md`). Codex was
given the full requirements doc verbatim plus the operator's established answer-patterns, briefed to
confirm-or-refute (not flatter), and asked to (A) give an overall read, (B) enrich, (C) name gaps as new
requirements, (D) challenge/pre-mortem the maximalism, (E) answer the deferred questions in the operator's
voice, and (F) leave its sharpest remaining questions with its own best guesses.

**Invocation** (per [[reference-codex-second-opinion]]):
`codex exec -m gpt-5.5 -c model_reasoning_effort="xhigh" -c approval_policy="never" -s read-only < brief.md`

**Disposition:** the operator reviewed the comparison and chose to roll *all* the enrichments in
immediately (no staged v2). The one item he questioned — the "structured JSON" canvas — was a misread
(model-vs-render split, where the operator only ever sees the rendered visual); R30 was written to encode
that as a guarantee. The accepted mechanics landed as R26–R39 in the requirements doc, with the
thin-slice principle added to Key Decisions and the on-behalf answers captured as planning defaults. One
divergence from Codex's on-behalf answers: the corpus-layout question (committed `docs/muse/` vs.
gitignored machine-local) was elevated to *Resolve before planning* rather than auto-answered, since
stated preference genuinely doesn't settle it.

---

## Codex deliverable (verbatim)

**A. Overall read.**

This is a sound requirements doc to plan against. Its biggest strength is that it correctly treats `/muse`
as a closed cognition loop, not a chat mode with nicer prompts. Its biggest risk is that the four
load-bearing surfaces are still specified more as product intent than as executable mechanics, especially
R5, R10, R12, R17, and R20.

Verdict: **plan-ready-with-fixes**. Do not trim the thesis, but add planning-grade mechanics before
implementation.

**B. Enrichment — the interesting thoughts.**

- **After-action trace, not in-session narration.** Keep methods invisible during F1, but emit a private
  post-session trace: "what moved, what stalled, which moves fed which seeds." This strengthens R6, R9,
  R10, SC1, and trust without breaking flow. **v1.**

- **Semantic canvas model before SVG.** Treat the canvas as a typed model, with nodes, claims, tensions,
  metaphors, clusters, and links, then render SVG/HTML from that model. This makes R11-R13 reliable enough
  to disagree with and prevents pretty-but-false diagrams. **v1.**

- **Collision ledger.** Foraging should not just resurface threads; it should record why a spark collided,
  what source triggered it, and whether the operator reopened. This strengthens R17, R18, R10, and SC3.
  **v1.**

- **Creative pressure gauges.** Add internal measures for novelty velocity, fixation, fragmentation, and
  closure pressure. These are the actual inputs the method engine needs to decide whether to focus,
  unfocus, randomize, or deepen. Strengthens R5, AE1, and SC1. **v1.**

- **Doubt quarantine taxonomy.** Split parked doubts into feasibility, ethics, market, implementation,
  taste, contradiction, and "operator discomfort." This keeps critique out of F1 while making F3 stronger
  for `/ideate`. Strengthens R2, R21, AE4. **v1.**

- **Re-entry ritual.** When reopening a thread, the partner should give the spark, the current visual
  model, the last unresolved metaphor, and one live invitation. This makes soak operational instead of
  just durable storage. Strengthens R16-R19 and F2. **v1.**

- **Method diet profile.** Track not only what works, but what overworks: prompts that annoy, shrink the
  field, produce generic output, or cause premature convergence. This protects R8 and makes R10 genuinely
  adaptive. **v1.**

- **Satellite provenance wrapper.** Every import from NotebookLM, Gemini, MindNode, Excalidraw, or Docs
  should come back with source, date, operator note, and "what it changed in the thread." This keeps
  satellites useful without making them authoritative. Strengthens R24-R25. **v1.**

**C. Gaps and missing requirements.**

- **R26. Flow-monitor inputs.** The method engine must observe explicit signals: novelty rate, repeated
  node revisits, operator affect markers, unresolved metaphors, canvas correction frequency, branch
  breadth, silence or stalling, and premature closure language.

- **R27. Flow-state detection rules.** The system must define detectable states for flowing, rut, stuck,
  too-focused, too-unfocused, and closure-pressure, with default moves for each and cooldowns to avoid
  prompt loops.

- **R28. Learning signal capture.** Each method move must capture inferred outcomes: operator continues,
  redirects, rejects, screenshots, reopens, graduates, marks useful, or abandons; explicit ratings are
  optional and post-session only.

- **R29. Canvas source model.** The canonical canvas artifact must be structured JSON with stable node
  IDs, labels, typed edges, clusters, and layout hints; SVG/HTML is a render output, not the source of
  truth.

- **R30. Canvas correction protocol.** Pointing, screenshotting, or natural-language correction must map
  to stable node IDs or named regions; every re-render should preserve identity unless the operator
  explicitly asks to split, merge, or rename.

- **R31. Critique escape hatch.** If the operator asks for a reality check inside `/muse`, the partner
  must not answer it in-session; it parks the request and offers to graduate, fork to `/ideate`, or record
  a doubt.

- **R32. Cold-start behavior.** On session one, before learned data exists, the partner must use a curated
  default method diet, seeded operator preferences, and rapid post-session learning rather than pretending
  personalization exists.

- **R33. Foraging safety envelope.** Foraging must define allowed sources, cadence, cost cap, maximum
  resurfacing volume, and suppression rules so it becomes useful collision, not nagging background noise.

- **R34. Completion heuristic.** Graduation remains operator-authoritative, but the partner may suggest
  readiness only when the canvas stabilizes, unresolved primitives decline, language stops changing, and
  doubts are sufficiently captured.

**D. Challenges — where the doc is wrong or over-committed.**

- **Maximalist v1: mostly right, but scope must be thin-sliced vertically.** I agree with the operator
  that critique-ban alone, canvas alone, or persistence alone does not prove the product. But "all four
  surfaces" should mean minimal closed versions of each, not full-depth foraging, full adaptivity, full
  satellite suite, and rich canvas all at once.
  Pre-mortem: the team builds four impressive demos that do not interlock, so the loop never actually
  closes.

- **Methods invisible by default: right in-session, wrong if permanently opaque.** R6 is correct for flow,
  but total invisibility fights SC1 because the operator cannot tell expert timing from random prompt
  variation. The fix is delayed inspectability: no labels during play unless asked, but a post-session
  trace should make the expertise legible.
  Pre-mortem: the partner feels like generic chat with a hidden prompt library, and trust never compounds.

- **Agent-rendered canvas: necessary, but currently aspirational.** The doc is right that visualization is
  non-negotiable and agent-rendered by default. But R11-R13 need a structured canvas model and correction
  protocol, or the canvas will become a decorative SVG generator rather than a shared substrate.
  Pre-mortem: the operator spends the session debugging the drawing instead of thinking through the idea.

**E. Answer the six deferred-to-planning questions on the operator's behalf.**

- **Corpus layout and persistence shape.**
  `[proposed — operator's likely call]` Use a saga-owned off-chain corpus with one directory per thread:
  `manifest.json`, `transcript.md`, `seeds.jsonl`, `doubts.jsonl`, `moves.jsonl`, `canvas/model.json`,
  `canvas/render.svg`, `sparks.jsonl`, and `satellites/`.
  Rationale: matches his plain text/JSON source-of-truth preference and keeps `/muse` out of saga
  work-state.

- **Canvas render format and pointing map.**
  `[proposed — operator's likely call]` Canonical canvas is structured JSON; rendered output is SVG first,
  optionally HTML later. Pointing maps through stable node IDs, visible labels, screenshot annotations, or
  natural-language references to named clusters.
  Rationale: faithful render matters more than direct editing; screenshot/pointing is steering, not the
  primary model.

- **Which satellites ship first and import formats.**
  `[proposed — operator's likely call]` Ship a generic source pack plus manual imports for NotebookLM,
  Gemini Canvas, MindNode, Excalidraw, and Google Docs, using Markdown, JSON, OPML, Excalidraw JSON, and
  pasted/exported text with provenance.
  Rationale: he explicitly rejected cutting satellites, but accepts manual round-trip in v1.

- **Foraging cadence, sensitivity, and cost.**
  `[proposed — operator's likely call]` Run local-source foraging on session close and on a bounded daily
  cadence, high precision over recall, with a small spark queue and no timer nags without a concrete
  collision.
  Rationale: he wants active incubation, but the trigger must be "this rhymes with your dormant thread,"
  not "remember this?"

- **How completion is detected versus operator-declared.**
  `[proposed — operator's likely call]` Operator declaration is authoritative; the partner may only
  suggest readiness when the model stabilizes, the canvas has few disputed primitives, and new turns
  elaborate rather than change the core shape.
  Rationale: "feels complete" is subjective, but the partner can notice closure pressure without forcing
  convergence.

- **How method-to-outcome learning is captured.**
  `[proposed — operator's likely call]` Capture inferred outcomes by default and optional post-session
  ratings, never in-session ratings. Use continuation, redirects, screenshots, reopenings, graduations,
  abandonment, and explicit "that moved it" language as signals.
  Rationale: methods stay invisible during flow, but the learning seam needs real fuel from day one.

**F. Sharpest remaining questions.**

- **What is the v1 runtime surface for the canvas?**
  Best guess: generate SVG/HTML files from the thread corpus and open them in the browser or viewer; do
  not build a full canvas editor yet.

- **How private is foraging allowed to be?**
  Best guess: local journal, diffs, and existing muse threads only in v1; wider web and app integrations
  later after the collision ledger proves value.

- **What happens when `/muse` material becomes obviously dangerous or operationally risky?**
  Best guess: still do not critique inside `/muse`; park the risk as a quarantined doubt and recommend
  immediate graduation or handoff to `/ideate` when the operator explicitly asks for judgment.

---

## Mapping: Codex's numbering → requirements-doc numbering

Codex emitted its own R26–R34. Folded into the doc they were renumbered to avoid colliding with the
existing R1–R25 and to group each under the right header. The enrichments in section B that were not
separate Codex requirements (after-action trace, collision ledger, re-entry ritual, method diet,
satellite provenance, doubt taxonomy) became their own requirements too.

| Codex item | Requirements-doc home |
|---|---|
| R26 Flow-monitor inputs | R26 |
| R27 Flow-state detection | R27 |
| R28 Learning-signal capture | R28 |
| R29 Canvas source model | **R30** |
| R30 Canvas correction protocol | **R31** |
| R31 Critique escape hatch | **R36** |
| R32 Cold-start behavior | **R35** |
| R33 Foraging safety envelope | **R34** |
| R34 Completion heuristic | **R37** |
| B1 After-action trace | R29 |
| B3 Collision ledger | R32 |
| B6 Re-entry ritual | R33 |
| B7 Method diet | folded into R29 |
| B8 Satellite provenance | R38 |
| B5 Doubt taxonomy | R39 (softened: typed at the airlock, not in-session) |
