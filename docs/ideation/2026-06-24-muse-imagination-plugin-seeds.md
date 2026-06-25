---
date: 2026-06-24
topic: muse-imagination-plugin
kind: imagination-seeds
maturity: imagination-seeds   # upstream of idea-ready; feeds /ideate
source: socratic imagination session (this transcript) + 2 verified tool-research sweeps
working-name: /muse
---

# /muse — Seed Document for `/ideate`

> This file is a **seed document**, not an implementation plan. Its job is to hand `/ideate`
> a set of grounded, divergence-ready seeds about a new pure-greenfield imagination command
> for the `saga` plugin. Scope, cost, and feasibility are **deliberately out of frame** — this
> is the "if you had all the time, money, and people" altitude. `/ideate` (then `/brainstorm`,
> `/plan`) is where grounding and convergence happen.

---

## Context — why this exists

The `saga` fuzzy front end is already rich, but it has a real hole:

| Command | Question it answers | Critique posture |
|---|---|---|
| `/office-hours` | "What's the right frame?" | diagnostic, single-session, route-only |
| `/ideate` | "What are the strongest ideas?" | **adversarial — cuts any idea with no articulated basis** |
| `/brainstorm` | "What should one idea mean?" | pressure-test one survivor into requirements |

The surprise from exploring the code: `/ideate` already does much of what felt missing —
constraint-flipping ("budget 10x or 0, team of 100 or 1"), cross-domain analogy,
assumption-breaking. So the gap is **not** "a divergence engine." The gap is the one rule
buried in `/ideate` Phase 3 — *"an idea with no articulated basis does NOT surface"* — which is
exactly what kills *"throw it at the wall, it's crazy, I can't justify it yet."*

**The genuine white space:** a place where critique and convergence are **banned**, where
ungrounded, half-formed, crazy seeds are allowed to live and mutate **across many days**, with a
partner who simultaneously keeps the thoughts flowing **and** documents/organizes them — a
**midwife for the thing on the tip of your tongue.** `/ideate` becomes the thing you graduate
*into* once a seed has mutated enough to be worth grounding.

**Decision (operator):** `/office-hours` in its current state hasn't earned its keep. `/muse`
**replaces** it — absorbing its useful frame-finding/routing as `/muse`'s tail-end "converge &
route" exit. So this is consolidation, not a 4th fragmenting front door.

**Meta-proof:** *this very session was a `/muse` prototype* — a multi-method imagination session
(Socratic questioning + research-grounded provocation + a partner documenting and organizing)
that midwifed the concept below. The dual provocateur+scribe role already proved itself here.

---

## The concept in one paragraph

`/muse` is the **pre-everything** creative front door: a critique-banned, multi-session
imagination space where you let thoughts flow and a partner (a) provokes them along with a
rotating toolkit of named creative methods, and (b) continuously captures and organizes them into
a durable, plain-text living canvas. The partner **adaptively decides** which method or visual
tool to engage based on the activity — and also offers you the choice, and obeys when you direct.
You work the thread over days; each session is a raw transcript that an end-of-session
**integration ritual** distills into structured seeds and folds into a single canvas view. When
something nameable finally surfaces, `/muse` frames it and routes it onward — most often to
`/ideate`, carrying its seeds (and a quarantined parking lot of doubts) forward.

---

## Design pillars (the settled shape)

1. **Midwife for the inchoate** — the soul is eliciting "the thing you can't quite put your
   finger on," keeping it flowing, never forcing premature shape.
2. **Critique is banned here** (the hard differentiator from `/ideate`). Doubts and feasibility
   flags are *captured but quarantined* in a parking lot — never acted on, never lost — and
   travel with the seeds to `/ideate`, which is where critique belongs.
3. **Dual role: provocateur + scribe/librarian** — the partner generates divergence AND maintains
   the durable record in the same loop. Not one or the other.
4. **Multi-method, not one method** — a library spanning eight families / ~70 catalogued
   techniques (below), composable, with a machine-readable registry the agent selects from (S26).
5. **Adaptive tool/method orchestration — three drivers** *(new, from operator)*:
   the agent **decides** (reads the activity, picks a method/tool), the agent **asks** (offers a
   fork), and the user **directs** ("give me a mind map of this now"). This is the saga
   operator-choice pattern applied to creative methods.
6. **Durability = plain-text spine + satellites** — local markdown/git is the agent-owned source
   of truth; richer/visual/cloud tools are satellites that round-trip back into the spine.
7. **Replaces `/office-hours`** — subsumes its router role as the converge-and-route exit.
8. **Routes forward** — the seam to `/ideate` (seeds graduate from critique-banned to
   grounded+filtered), or `/brainstorm` / `/plan` / "drop it."

---

## The method library — eight families (~70 techniques catalogued)

A full catalogue (grounded in the two operator-supplied sources — lateralaction.com/creative-thinking
+ the Wikipedia creativity-techniques list — extended with the design-thinking / TRIZ / de Bono /
Synectics canon) is the appendix to this doc. Working taxonomy, grouped by *what it does to your
thinking* (not origin):

| # | Family | Representative techniques | Role in /muse |
|---|---|---|---|
| 1 | **Divergent generation** | brainstorming, Crazy 8s, SCAMPER, free association, brainwriting/6-3-5, SIL | produce raw volume |
| 2 | **Reframing / assumption-breaking** | five-whys→How-Might-We, first-principles, inversion, abstraction laddering | change the question |
| 3 | **Provocation / lateral / random** | de Bono PO, random word, Oblique Strategies, wishful thinking, incubation | inject deliberate irrelevance |
| 4 | **Combination / morphological** | Zwicky box, forced connections, Synectics, biomimicry, lotus blossom, TRIZ | recombine parts |
| 5 | **Perspective / role-shift** | Six Hats, Disney method, rolestorming, extreme users, personas | change who is thinking |
| 6 | **Future / vision / speculative** | backcasting, pre-mortem/pre-parade, future wheel, design fiction | think from another time |
| 7 | **Convergent / selection** ⚠️ | NUF, impact-effort, dot voting, affinity/KJ | THE BRAKE — walled off (S27) |
| 8 | **Visual / spatial** | mind/concept maps, storyboards, rich pictures, journey maps | think on a surface |

**Design principle (earned from the catalogue):** families 1–6 + 8 are the imagination *engine*;
**family 7 is the brake.** Mixing selection prompts into a divergence session is the single most
common way these techniques backfire — so `/muse` walls family 7 off, surfacing it only at the
converge-and-route exit (the absorbed `/office-hours` role).

**Highest-fit for a solo human + AI partner over text** (catalogue shortlist): SCAMPER, random-word,
first-principles, five-whys→HMW, Six Hats, pre-mortem/pre-parade, Synectics analogy-hunting,
morphological/Zwicky, Disney method, backcasting, lotus blossom, rolestorming. ⚠️ Group/whiteboard
techniques (brainwriting, Charette, Crawford slip, Delphi, dot-voting, affinity-wall) are weaker
solo fits — `/muse` may *simulate* the missing voices but must flag it as a stand-in (S28).

Plus **inchoate-elicitation techniques** for "tip of the tongue" work: reflective mirroring
("say more"), forced metaphor ("if this were an animal / building / song…"), the magic-wand
question, desire-five-whys (why do you *want* this, five levels down), and constraint provocation.

---

## The artifact + tooling landscape (verified)

Every tool below was checked against one test: **the durable source of truth is plain text an
agent reads/writes across sessions; a visual tool earns a place only if an agent can
programmatically create AND update it and round-trip it back to text.**

### First-class (operator selected all four)

- **JSON Canvas spine** (`.canvas`, open Obsidian spec, jsoncanvas.org) — the agent writes the JSON
  by hand (two arrays: `nodes[]` ~6 fields each + `edges[]`), perfect git diffs, fully local. This
  is the **single living spatial canvas** that "represents all the other documents" — a *thinking
  surface*, not just an output: ideas as nodes you cluster, connect, rearrange. The one thing
  Mermaid can't be while staying pure text.
- **Markmap + D2/Kroki** — Markmap turns *ordinary markdown* into a zoomable mindmap with zero new
  syntax (`npx markmap-cli --offline`); D2 is a layout-controllable diagram DSL; **Kroki** is one
  HTTP call that renders *any* text-diagram dialect (Mermaid/D2/Graphviz/PlantUML/Excalidraw/…) to
  SVG/PNG, so the text never gets trapped in one renderer. This is the "Mermaid falls short" fix.
  - *Mermaid's weakness, pinpointed:* its `mindmap` type has no direction/layout/placement control
    (open bug mermaid-js #5653) and no freeform canvas at all — auto-layout only.
- **HTML UI/UX prototypes** — the agent writes a single-file `.html` (Tailwind/Pico/DaisyUI via
  CDN), opens it `file://` in the **Chrome MCP already connected this session**, screenshots,
  edits, repeats. Real visual mockups in the loop, no build/server/auth. Net-new capability nothing
  in the family does today. (React via v0/shadcn is an opt-in "promote to components" step — it
  needs a dev server before a screenshot is possible.)
- **Google satellite ring** — the **Drive MCP connected this session** can mint native Google
  Docs/Sheets from text, read them back as clean text, and full-text-search a corpus, so an
  agent-owned Drive/Docs corpus is real. NotebookLM + Gemini Canvas are **generators** you operate
  by hand; their output round-trips back into the spine via "export to Docs" → agent reads it.

### Correction on NotebookLM (operator was right)

My earlier "no path" was too strong. Accurate statement:
- **No *official* consumer write API** (the real NotebookLM Enterprise API is GCP-license/IAM-gated,
  off-limits to a consumer AI Ultra account).
- **But unofficial automation exists** — community projects like `teng-lin/notebooklm-py` and
  `jacob-bd/notebooklm-mcp-cli` drive NotebookLM via UI automation / reverse-engineered endpoints.
- **Tradeoff:** ToS-gray and brittle (breaks when Google changes the UI). → a **spike-worthy
  seed**, not a closed door.

### Other satellites (text-spine stays primary)

- **MindNode** (your seed) is *not* GUI-only — it round-trips Markdown/OPML/FreeMind and is
  drivable on Mac via AppleScript/Shortcuts; keep Markdown/OPML as the spine, MindNode as a render
  satellite.
- Cloud SaaS (Miro/Figma/Penpot/Whimsical) have create APIs/MCPs but are OAuth/paid-gated and have
  no diffable text source — satellites only, never the source of truth.

---

## The durability architecture

```
                       ┌─────────────────────────────────────────┐
   per-session         │   LOCAL PLAIN-TEXT / GIT SPINE (truth)   │
   raw transcripts ──▶ │   docs/muse/<thread>/                    │
   (1..many sessions)  │     ├─ sessions/NNN-raw.md  (transcripts)│
                       │     ├─ seeds.md            (distilled)   │
   end-of-session      │     ├─ canvas.canvas       (living view) │ ◀── single canvas view
   INTEGRATION RITUAL ─┤     ├─ wonder-log.md       (what-ifs)    │
   (raw → distilled →  │     └─ parking-lot.md      (quarantine)  │
    canvas update)     └───────────────┬─────────────────────────┘
                                        │  round-trip via export / read-back
                       ┌────────────────▼─────────────────────────┐
                       │  SATELLITES (human-driven generators)     │
                       │  NotebookLM · Gemini Canvas · MindNode ·  │
                       │  Drive/Docs corpus · Miro/Figma           │
                       └───────────────────────────────────────────┘
```

Principle: **the LLM can always reconstruct full context from the plain-text spine alone.**
Satellites enrich but never become load-bearing. The **integration ritual** is the scribe role
made concrete — every session ends by distilling the raw transcript into seeds and folding new
material into the canvas, so the thread compounds instead of sprawling.

---

## Open questions / forks for `/ideate` to diverge on

- **Spine location:** local-git primary (default here) vs. Drive/Docs corpus vs. true hybrid?
- **Canvas as thinking-surface vs. output-only:** does the agent *reason over* the `.canvas`
  (rearrange/cluster nodes as a move) or only emit it at integration time?
- **Divergence mechanism:** single-agent in-conversation vs. parallel **mutation fan-out** (N
  agents each applying a different SCAMPER op / provocation / persona, returning variants — like
  `/ideate`'s frame agents but with the convergent filter removed)?
- **Parking-lot discipline:** how do quarantined doubts travel to `/ideate` without leaking
  critique back into the flow?
- **Office-hours migration:** clean replace, or keep a thin `/office-hours` alias that forwards?
- **The rubric:** what makes a *good* `/muse` artifact? (operator explicitly wants this — see S12.)
- **On-chain vs off-chain:** off-chain like office-hours/ideate (default), or a durable saga
  "imagination thread" so `/resume` and the journal can see it?

---

## Technique applied — a SCAMPER pass on `/muse` (dogfood, 2026-06-24)

To pressure-test the concept with one of its own methods, here is a live SCAMPER mutation of `/muse`
itself. Each operator produced a real new direction; the strongest became seeds **S17–S26**. (This
section *is* evidence the doc evolved via a named technique — the thing `/muse` would do.)

- **Substitute** — voice / stream-of-consciousness capture instead of typing (S18); a *panel of
  named muses* instead of one partner (S17).
- **Combine** — the engineering journal (LEARNINGS/DECISIONS) as raw provocation fuel + cross-thread
  pollination (S23).
- **Adapt** — improv "yes-and" as the *enforced* critique-ban contract (S19); spaced-repetition
  resurfacing of dormant seeds + a between-session nudge (S22).
- **Modify/Magnify** — mass unfiltered divergence: 100 variants that just sit (S24).
- **Put to other use** — `/muse` as a general-purpose creative substrate, not just product ideas
  (S25); parking-lot doubts repurposed as a provocation generator.
- **Eliminate** — pure-capture / silent-scribe mode, AI generates nothing (S20); eliminate the
  session boundary (one ambient thread).
- **Reverse** — reversed provocation: the AI throws wild seeds and *you* mutate them (S21);
  artifact-first ideation, start from a random image/object.

## THE SEEDS (hand these to `/ideate`)

> Format matches the `/ideate` input contract: each seed is verbatim-capturable with a tagged
> basis (`direct:` code/transcript, `external:` named prior art, `reasoned:` first-principles).
> `/ideate` will feed these into its frame agents to build on / challenge / combine, then ground
> and filter them.

**S1 — Critique-banned divergence zone with a quarantine parking lot.**
A creative space where convergence/critique is *structurally forbidden*; doubts are captured to a
parking lot and travel forward to `/ideate`, never acted on in-session.
`basis — direct:` `/ideate` Phase 3 "an idea with no articulated basis does NOT surface" is the
exact filter `/muse` must invert.

**S2 — Dual-role partner: provocateur + scribe/librarian in one loop.**
The agent generates divergence and maintains the durable organized record simultaneously.
`basis — direct:` operator: "a partner who not only helps keep them flowing, but documents and
organizes them."

**S3 — Multi-method library (4 families), composable.**
Mutation operators + Provocation/lateral + Perspective ensembles + Future/vision, swappable mid-session.
`basis — external:` SCAMPER, de Bono (Six Hats / lateral thinking / PO), Disney method, speculative
design, TRIZ/SIT, morphological analysis, backcasting.

**S4 — Adaptive tool/method orchestration with three drivers.**
Agent-decides (reads the activity), agent-asks (offers a fork), user-directs. Not a fixed pipeline.
`basis — direct:` operator: "the agent should be making some decisions… also asking the user or
the user directing as well."

**S5 — Inchoate-elicitation techniques ("tip of the tongue").**
Reflective mirroring, forced metaphor, magic-wand question, desire-five-whys, constraint provocation.
`basis — reasoned:` the stated soul is surfacing pre-verbal intent; these are the named techniques
for exactly that, distinct from `/ideate`'s idea-generation frames.

**S6 — Parallel mutation fan-out (divergence-only).**
N agents each apply a different SCAMPER op / provocation / persona to a seed and return variants —
`/ideate`'s frame-agent fan-out with the convergent filter removed.
`basis — direct:` `/ideate` Phase 2 dispatches N parallel frame agents; reuse the mechanism, drop
the Phase 3 cut.

**S7 — JSON Canvas as the living spatial thinking surface + single view.**
Agent-written `.canvas` (open spec) the user and agent cluster/connect/rearrange; the one view over
all thread docs.
`basis — external:` JSON Canvas 1.0 open MIT spec (jsoncanvas.org/spec/1.0) — agent writes the JSON
directly, clean git diffs.

**S8 — Markmap + D2/Kroki text-spine diagram layer (the Mermaid-falls-short fix).**
Markdown→mindmap with zero new syntax; D2 for controllable diagrams; Kroki to render any dialect.
`basis — external:` Markmap CLI; D2 (terrastruct); Kroki HTTP render gateway; Mermaid mindmap
limitation = open bug mermaid-js #5653.

**S9 — Agent-driven HTML/CSS UI/UX prototypes via the Chrome MCP.**
Single-file HTML (Tailwind/Pico CDN) → open `file://` → screenshot → iterate. Net-new visual output.
`basis — direct:` two Chrome MCPs are connected this session; the author→render→screenshot loop is
live now.

**S10 — Google satellite ring (Drive corpus + NotebookLM/Gemini round-trip).**
Agent mints/reads a Drive/Docs corpus; NotebookLM/Gemini are human-driven generators whose output
returns via Docs export.
`basis — direct:` Drive MCP `create_file`(text→native Doc) + `read_file_content` are available this
session; `external:` NotebookLM has no official consumer API.

**S11 — Unofficial NotebookLM automation spike.**
Evaluate `notebooklm-py` / `notebooklm-mcp-cli` to close the manual generate+export gap, eyes open
to the ToS/brittleness risk.
`basis — direct:` operator-supplied repos `teng-lin/notebooklm-py`, `jacob-bd/notebooklm-mcp-cli`.

**S12 — A rubric for imagination artifacts.**
Define what makes a *good* `/muse` output (e.g., seed clarity, divergence spread, canvas coherence,
forward-routability) — the quality bar for a session.
`basis — direct:` operator: "I would need a rubric for the artifacts… what is the outcome of any
imagination session."

**S13 — End-of-session integration ritual.**
Every session ends by distilling its raw transcript into seeds and folding new material into the
canvas, so the thread compounds.
`basis — direct:` operator: "at the end of any given session there is something that is taking the
new information and integrating it."

**S14 — Multi-session persistence (resume a muse thread over days).**
A `/muse` thread is a durable, resumable corpus, not a one-shot — the agent rehydrates full context
from the plain-text spine.
`basis — direct:` operator: "working back and forth potentially over days and days."

**S15 — Replace `/office-hours`; subsume its router as `/muse`'s converge-and-route exit.**
When something nameable surfaces, `/muse` frames it and routes to `/ideate` / `/brainstorm` /
`/plan` / drop.
`basis — direct:` operator: "throw away office hours, add this new thing in, with a new name";
`/office-hours` Phase 3 routing rubric is the behavior to absorb.

**S16 — Name: `/muse`** (alternates carried: `/imagine`, `/wonder`, `/percolate`).
`basis — direct:` operator selected `/muse`.

### Seeds from the SCAMPER pass + technique catalogue (S17–S28)

**S17 — Persona panel of named, summonable muses.**
Summon distinct named muses (the Contrarian, the Child, the Futurist, the Naturalist…) by name
mid-session instead of one undifferentiated partner.
`basis — reasoned:` SCAMPER-Substitute on the single-agent model + catalogue family 5
(rolestorming / personas); divergence improves when "who is thinking" rotates.

**S18 — Voice / stream-of-consciousness capture.**
Speak the flow instead of typing it; the scribe transcribes and organizes. Reuses the existing
redis-channel voice mode.
`basis — direct:` redis-channel voice source mode exists in this repo; `reasoned:` flow is faster
spoken than typed (SCAMPER-Substitute on the input channel).

**S19 — Improv "yes-and" as the enforced critique-ban contract.**
Make "yes-and" the literal interaction rule that *operationalizes* the critique ban — the agent must
build on, never block.
`basis — external:` improv theatre's core rule; `reasoned:` the concrete mechanism that enforces
pillar 2 instead of merely asserting it.

**S20 — Pure-capture / silent-scribe mode.**
A mode where the AI generates nothing and only keeps you flowing + organizes — the scribe half
alone, on demand.
`basis — direct:` operator soul "let the thoughts just flow… a partner who documents and organizes";
`reasoned:` SCAMPER-Eliminate isolates the scribe from the provocateur.

**S21 — Reversed provocation + artifact-first ideation.**
Invert who provokes: the AI throws wild seeds and you mutate them; or start from a random
image/object and work backward to a problem.
`basis — reasoned:` SCAMPER-Reverse on provocation direction; `external:` random-stimulus /
artifact-first lateral techniques.

**S22 — Spaced resurfacing of dormant seeds + between-session nudge.**
The muse resurfaces a seed days later ("you wondered about X three days ago — still itching?") and
can send a daily digest that keeps a thread warm.
`basis — external:` spaced repetition; `direct:` operator "over days and days" — a multi-session
thread needs a heartbeat.

**S23 — Cross-thread pollination + journal-as-fuel.**
A seed in thread A can mutate a seed in thread B; muse threads mine `docs/engineering-journal/`
(LEARNINGS/DECISIONS) for raw provocation material.
`basis — reasoned:` SCAMPER-Combine; `direct:` the repo's engineering journal is existing raw stock.

**S24 — Mass unfiltered divergence.**
Generate 100 wild variants of a seed and let them *sit* — no scoring, no cut — as a deliberate
volume move.
`basis — reasoned:` SCAMPER-Magnify on divergence; aligns with pillar 2 (no filter here) and
contrasts `/ideate`'s capped survivor target.

**S25 — `/muse` as a general-purpose creative substrate.**
Not just product/architecture ideas — naming, narratives, problem-reframing, writing, even life
decisions. The engine is domain-agnostic.
`basis — reasoned:` SCAMPER-Put-to-other-use; the method families are domain-neutral, so
constraining to product is an arbitrary narrowing.

**S26 — Machine-readable method registry with adaptive selection.**
A loadable registry (`family`, `name`, `one_liner`, `solo_ai_fit`, `needs_group`) the agent reads to
*adaptively pick* a technique for the moment — powering pillar 5's three drivers.
`basis — external:` the ~70-technique catalogue (8 families) compiled this session; `reasoned:`
adaptive orchestration needs a structured menu to choose from.

**S27 — Wall off convergent/selection techniques (family 7).**
Keep NUF / impact-effort / dot-voting / affinity OUT of the default divergence flow; surface them
only at the converge-and-route exit.
`basis — external:` catalogue insight — "family 7 is the brake; mixing selection into divergence is
the #1 way these tools backfire."

**S28 — Honest group-technique simulation.**
When a technique needs many independent humans (brainwriting, Crawford slip, Delphi), the AI may
simulate the voices but must flag it as a stand-in, not the real mechanism.
`basis — external:` catalogue ⚠️ note on group-dependent techniques; `reasoned:` validation
discipline — never present a simulation as the genuine multi-human process.

---

## How this gets used (next steps)

1. **This file is persisted** here in `docs/ideation/` so `/ideate`'s Phase 0 resume scan can find
   it (or hand the path to `/ideate` directly as the seed source).
2. **Run `/ideate`** on it — the 28 seeds enter the candidate pool, get grounded and adversarially
   filtered, and surface as ranked survivors with a revivable cut.
3. **`/brainstorm`** the strongest survivor into requirements, then `/plan` to actually scope and
   build `/muse`. **Scope/cost/feasibility belong there — not here.**

## Downstream build map (DEFERRED — for `/plan`, not now)

Captured so nothing's lost; intentionally not elaborated (this is imagination time):
- `plugins/saga/commands/muse.md` + `plugins/saga/skills/muse/SKILL.md` (+ `references/`).
- Version-bump surfaces: `plugins/saga/.claude-plugin/plugin.json`,
  `.claude-plugin/marketplace.json`, `plugins/saga/CHANGELOG.md`.
- Drift-guard tests: `tests/test_saga_plugin.py`, `tests/test_saga_docs_coverage.py`,
  `tests/test_saga_doc_formatting.py`.
- Office-hours retirement/migration.
- Output home: `docs/muse/`.
- Method registry artifact: a machine-readable `methods.{json,yaml}` (family / name / one_liner /
  solo_ai_fit / needs_group) loaded for adaptive selection (S26); the research agent can emit it.

---

## Verification (does this seed doc do its job?)

- **Consumable by `/ideate`:** every seed has a title + 2–4 sentence summary + a tagged
  `direct:`/`external:`/`reasoned:` basis → satisfies the `/ideate` input contract (so none get
  auto-dropped for "no articulated basis").
- **End-to-end check:** persist the doc, invoke `/ideate` against it, confirm the seeds appear as
  candidates and produce ranked survivors + a revivable cut. That is the real test that this
  document is a working seed for the next stage.
