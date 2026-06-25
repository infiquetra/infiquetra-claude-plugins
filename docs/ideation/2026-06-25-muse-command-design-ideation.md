---
date: 2026-06-25
topic: muse-command-design
focus: design the /muse saga command from its 28-seed imagination doc
scope: broad
repo: infiquetra-claude-plugins
maturity: idea-ready
---

# Ideation: /muse Command Design

Ranked survivors from running the 28-seed `/muse` imagination doc
(`docs/ideation/2026-06-24-muse-imagination-plugin-seeds.md`) through `/ideate`: 6 frame agents +
3 grounding agents generated ~50 candidates, the 28 seeds entered the same pool, and the adversarial
filter cut everything that re-litigated a settled decision, lacked a real consumer, or only restated
a stronger idea. Scope/cost still belong downstream — this is `idea-ready`, one rung below
`/brainstorm`.

## Grounding Context

**Repo:** `infiquetra-claude-plugins` — a Claude Code plugin marketplace; `saga` is a skills-based
plugin. A new command is `commands/muse.md` (thin launcher) + `skills/muse/SKILL.md` (phased engine)
+ `references/` + version surfaces (`plugin.json`, `marketplace.json`, `CHANGELOG.md`, drift-guard
tests) + a `docs/commands.md` row. The fuzzy front end /muse slots into: `/office-hours`
(frame-finding, off-chain, hard gate, hardcoded in tests + routing target in `/ideate` ×5 and
`/brainstorm`), `/ideate` (divergent→convergent, off-chain, **Phase 3 cuts any idea with no
articulated basis** — the exact filter /muse inverts), `/brainstorm` (deepen one idea). Hard journal
constraints that shaped the filter: diagram deps (Mermaid/PNG/Graphviz/D2) are **rejected**
(DECISIONS `{#saga-docs-source-model}`); the **dead-wiring rule** cuts any artifact lacking a real
producer *and* consumer; Think-phase commands are **off-chain** and don't consume the operator-choice
framework; the **self-modifying-engine gate** allows journal reads but makes any journal write
propose-diff-and-wait.

**Context-libraries:** None consulted — the topic is entirely about this repo's saga plugin.

## Topic Axes

- A1 — Partnership & elicitation (the interaction contract + drawing out inchoate intent)
- A2 — Method engine (the creative-technique library, adaptive selection, divergence mechanics)
- A3 — Durability & continuity (plain-text spine, integration ritual, multi-session memory, rubric)
- A4 — Tooling & visual surfaces (canvas/diagram/HTML/Google-satellite render & AI integrations)
- A5 — Lifecycle fit & boundary (office-hours disposition, routing to /ideate, on/off-chain, the
  critique-ban boundary)

## Ranked Survivors

### 1. Structural critique-ban (yes-and contract + ban-by-absence)

Enforce "no critique here" as architecture, not instruction — the provocateur role has no evaluative
affordance, can't reference its own prior output, and runs a yes-and contract with a named violation
list.

/muse's one distinct claim is being the only critique-banned space in saga. Make the ban structural
three ways: a yes-and output contract with an explicit violation list (no "but", no feasibility
question, no "have you considered the downside") plus a per-turn self-check; ban-by-absence — no
ranking, scoring, voting, or selection code paths exist in the muse engine, only in `/ideate`; and
the generator may not reference or build on its own prior output within a riff, forcing genuinely
blind variation.

Diehl & Stroebe (1987) show a single early negative evaluation cuts session output ~25% and operates
below conscious belief, so a merely-stated ban erodes turn by turn — especially against a base model
whose anti-sycophancy training makes every other Think command "push hard." Limb & Braun (2008)
ground it neurologically: spontaneous generation needs the self-monitor off, and an absent affordance
cannot be violated where an instruction can.

The risk is feeling robotic or refusing legitimate clarifying questions — the line between "clarify
to keep flow" and "evaluate" needs careful drafting. Forbidding self-reference within a riff also
limits the partner's ability to deliberately build a thread, a real tension with the scribe role (S2)
the build must resolve.

| field | value |
|-------|-------|
| basis | `external:` Diehl & Stroebe 1987 (evaluation apprehension); Limb & Braun 2008 PLOS ONE (DLPFC suppression); Dilts Disney strategy — plus `direct:` all 3 existing Think commands push hard (critique-ban is structurally new) |
| confidence | 92 |
| complexity | Med |
| axis | A1 |
| status | Unexplored |

### 2. Text-only spine — cut the canvas/diagram seeds, satellites are opt-in spikes

Ship /muse as a pure plain-text engine: drop JSON Canvas (S7) and Markmap/D2/Kroki (S8) entirely, and
gate every external tool (HTML/Google/NotebookLM) behind an explicit opt-in spike, never the default
path.

The durable spine is markdown only. JSON Canvas and the diagram layer are cut — not deferred with
hope — and the HTML-prototype, Drive/Docs, and NotebookLM satellites become labeled spikes a user
opts into, never wired into v1's flow.

DECISIONS `{#saga-docs-source-model}` already rejected Mermaid/PNG and Graphviz/D2/Python-Diagrams as
dependencies, and JSON Canvas/Markmap/D2/Kroki have zero repo foundation — four independent frames
flagged S7–S11 as re-litigating a settled decision. Independently, laying out and connecting nodes on
a canvas is itself a structuring (convergent) act that re-engages the self-monitor the critique-ban
exists to keep off.

This loses the "living visual canvas" the operator was drawn to, and some spatial-thinking value is
real. Revisit-when: ship the canvas only once the agent provably reasons over the `.canvas` as a move
(rearranging nodes changes its next provocation), or `/ideate`'s input contract is extended to ingest
it.

| field | value |
|-------|-------|
| basis | `direct:` DECISIONS `{#saga-docs-source-model}` (diagram deps rejected; zero repo foundation) + the dead-wiring rule (canvas has a producer but no consumer) |
| confidence | 90 |
| complexity | Low |
| axis | A4 |
| status | Unexplored |

### 3. No new artifact — a typed handoff straight into /ideate's seed inbox

/muse produces no `docs/muse/` corpus of its own; it appends seeds (each with a "basis-pending" slot)
directly into the one surface with a real consumer — `/ideate`'s seed input — through a stable typed
contract.

Instead of inventing an output directory that risks dead-wiring, /muse writes typed seeds carrying
origin-spark, session-date, and an empty basis slot `/ideate` later fills. The converge-and-route exit
is an airlock where the operator — still critique-free — attaches a candidate basis to the seeds they
choose to carry forward, so what reaches `/ideate`'s Phase-3 filter already has the articulated basis
it demands.

The dead-wiring rule cuts any artifact lacking a real producer and consumer, and `/ideate` ingesting
seeds is the only named consumer; a typed contract makes that wiring real and mechanical. It also
defuses the "graduation cliff" — handing raw ungrounded seeds into `/ideate`'s basis-cut would
clear-cut the user's imagination and punish them for using /muse as intended.

Coupling /muse's output format to `/ideate`'s input contract means the two evolve together, a
versioning burden. The airlock adds a step at the exact moment the user wants to stop, so it must stay
optional and lightweight.

| field | value |
|-------|-------|
| basis | `direct:` dead-wiring rule (LEARNINGS `{#dead-wiring-needs-producer-and-consumer}`); `/ideate` Phase 3 basis-cut; `/ideate` is the only named consumer |
| confidence | 88 |
| complexity | Med |
| axis | A5 |
| status | Unexplored |

### 4. Don't replace /office-hours — sit upstream as its critique-banned opposite

Keep `/office-hours`; /muse ships as a distinct command strictly upstream of `/ideate`, claiming the
genuinely-empty "critique-banned, frame-dissolving" niche rather than absorbing office-hours'
frame-finding router (a large surface change).

Reverse the seed doc's "replace office-hours" decision for v1. `/office-hours` finds a frame
(converges); /muse refuses to settle one (diverges) and routes only into `/ideate` — opposites at
adjacent positions, not competitors for one slot. /muse stays invisible to office-hours, so no
hardcoded test, `/ideate` routing reference, or `/brainstorm` bounce has to change.

The grounding shows `/office-hours` is hardcoded in multiple tests and referenced as a routing target
in `/ideate` (×5) and `/brainstorm` — replacing it is a large, risky surface change, while
decoupling is a small footprint. /muse's distinct claim (critique-banned) doesn't require owning the
front-door router role office-hours already fills.

This adds a fourth Think-phase command, cutting against the repo's recorded 17→7 anti-fragmentation
direction — a real tension a skeptic will raise. Revisit-when: only fold or replace office-hours
after /muse has proven seed-yield through `/ideate` on several real threads.

| field | value |
|-------|-------|
| basis | `direct:` grounding — office-hours hardcoded in tests + `/ideate` ×5 + `/brainstorm`; CLAUDE.md plugin-surface discipline; the 17→7 grooming direction |
| confidence | 85 |
| complexity | Low |
| axis | A5 |
| status | Unexplored |

### 5. Incubation engine — spaced resurfacing of dormant seeds across sessions

Make /muse genuinely multi-session by re-surfacing aging, never-promoted seeds at session start (and
when a live thread peaks), treating cross-session persistence as the incubation mechanism rather than
mere storage.

Seeds persist in an addressable, append-to-top log mirroring the journal's `{#slug}` grammar, so any
later session, the agent, or a human can deep-link one. A small rotating set of old seeds re-floats at
session start ("a 6-week-old spark you never took anywhere"), and the agent can drag an older parked
seed into the live session when a new thread peaks — energy-timed, not just calendar-timed.

Wallas incubation and the broader literature say an unsolved fragment strengthens in the background
via spreading activation, so persistence-plus-resurfacing IS the creative mechanism, not a
convenience; addressability is the precondition for both resurfacing and cross-thread pollination, and
collisions scale superlinearly with corpus size, so value compounds with use.

Resurfacing risks nagging or noise if the cadence is wrong, and it must stay off-chain with any
journal write as propose-diff-and-wait per the self-modifying-engine gate. Storing an addressable
corpus also re-opens the "what exactly persists" question survivor #3 tries to keep minimal — a
tension to resolve.

| field | value |
|-------|-------|
| basis | `external:` Wallas 1926 incubation (Frontiers 2014); Johnson slow-hunch / commonplace books — plus `direct:` the repo's journal `{#slug}` append-to-top grammar as the reuse pattern |
| confidence | 82 |
| complexity | Med |
| axis | A3 |
| status | Unexplored |

### 6. Journal-as-fuel + auto-seed — /muse never starts from a blank page

Open each session saturated, not empty — auto-seed provocations from the existing engineering-journal
corpus, recent diffs/ticks, prior muse seeds, and any artifact the operator is actually looking at, so
capture begins as reaction.

On invocation /muse reads (never writes) the journal (LEARNINGS/DECISIONS/ARCHIVE/QUEUED) and other
repo substrate and collides dormant fragments with the current spark; it can also riff directly from a
concrete artifact the operator pastes (a file, screenshot, error) rather than a verbal summary. The
blank page — the first silent critic ("is this idea good enough to write down?") — is removed.

Commonplace-book practice and the slow-hunch model show capture is friction-free when you react to
existing material and organize at review time; journal-read is explicitly allowed by the
self-modifying-engine gate, and the journal-as-fuel consumer (S23) is already named. Riffing from the
actual artifact also preserves the un-pruned weirdness a verbal summary has already edited out.

Auto-seeding can anchor the session on the loudest thing in the corpus, narrowing divergence rather
than widening it — the opposite of the goal unless balanced with deliberately-unrelated collisions.
The richer the journal, the more reading cost per session.

| field | value |
|-------|-------|
| basis | `external:` commonplace books / Johnson slow-hunch; Toyota genchi genbutsu (artifact-first) — plus `direct:` self-modifying-engine gate (journal reads allowed); seed S23 |
| confidence | 80 |
| complexity | Med |
| axis | A3 |
| status | Unexplored |

### 7. Data-driven method engine — registry + silent selection + blind-variation mechanics

Build the multi-method library as a registry of small reference files the orchestrator selects from
silently by default (from a ~12 hot-set, not a 70-item menu), stocked with divergence mechanics that
enforce blind variation.

Each creative method (yes-and, reversed provocation, negative-space/notan elicitation, persona shift,
Disney roles, mutation fan-out) is an addressable `references/` entry — data, not prose buried in
SKILL.md — so methods drop in without touching command logic and the orchestrator reasons over them
as objects. The default driver is agent-decides-silently from a curated hot-set; the full catalogue is
reached only on explicit user direction. The divergence mechanics deliberately manufacture blindness:
an "exquisite-corpse" fan-out where each agent sees only the prior fragment, and an "apophenia" move
that collides maximally-unrelated seeds and invents a connection rather than ranking by similarity.

A 70-technique registry with no opinionated default is a config burden masquerading as flexibility,
and asking the user to shop a menu mid-flow is itself an evaluative pause; a silent hot-set default
keeps them generating. BVSR (Campbell 1960; Simonton 2011) says variation must be blind to reach
genuine novelty, so plain parallel fan-out aimed at one target under-delivers — context-starvation
manufactures the real thing.

A registry plus adaptive selection plus multiple divergence mechanics is the most build-heavy
survivor; over-engineering the method layer before the core loop is proven is a real risk, and silent
selection reduces operator visibility into why a given provocation appeared.

| field | value |
|-------|-------|
| basis | `direct:` seeds S26/S4/S3 + the `references/` build pattern — plus `external:` Campbell 1960 / Simonton 2011 BVSR (blindness); Surrealist exquisite corpse |
| confidence | 78 |
| complexity | Med |
| axis | A2 |
| status | Unexplored |

## Did not survive (revivable)

Explicit rejection is the quality mechanism. Cut ideas keep stable ids so they can be revived
(re-entering the Phase 3 filter with new evidence). Several are strong but deferred (v2), not wrong.

| id | title | summary | reason | status |
|----|-------|---------|--------|--------|
| R1 | Replace /office-hours wholesale (S15) | /muse absorbs office-hours' router and retires it | Large surface (hardcoded tests + /ideate ×5 + /brainstorm); survivor #4 gets the niche at far lower risk. Revisit after /muse proves seed-yield | rejected |
| R2 | Mode toggle, not a command | A `--divergent` posture flag any Think command enters | A flag can't carry the multi-session spine or method engine; loses to #1+#4. Real if /muse stays tiny | rejected |
| R3 | Merge /muse into "ideate-opens-divergent" | Collapse the front end; /ideate just starts critique-banned | Contradicts the operator's settled "ship a distinct command" decision and entangles /ideate's filter; an /office-hours-level strategy question | rejected |
| R4 | Bidirectional: /ideate's cut pile feeds /muse | /ideate's revivable cuts re-enter /muse as freed-of-grounding seeds | Elegant, closes dead-wiring both ways — but v2: depends on #3's handoff existing first | rejected |
| R5 | Kept/cut feedback loop tunes methods | Harvest /ideate's filter verdicts to bias /muse's method selection | Deepest compounding loop, but pure v2: needs #3 + #7 and many runs of data | rejected |
| R6 | Unattended/ambient divergence | Fan out mutations while the operator is away; return to a harvest | Incubation-as-feature is compelling but high-complexity background agents + ungrounded-volume-with-no-attention risk | rejected |
| R7 | No session boundary / eternal thread | One never-closing ambient muse channel per repo | Fights the off-chain scratch model; the session is a useful unit for capture + resurfacing; R8 is the lighter realization | rejected |
| R8 | Persist a standing prompt, not state | Store one line ("you were circling X — still?"), not a corpus | Loses to #5's addressable seed log, which is what enables resurfacing + pollination; can't pollinate what you don't store | rejected |
| R9 | Voice / stream-of-consciousness capture (S18) | Speak the flow; redis-channel voice transcribes | Real friction reducer but capability-gated on a voice-capable router; a mode, post-v1 | rejected |
| R10 | No-AI provocation deck (S-variant) | /muse as an Oblique-Strategies-style deck, zero generation | Illuminates that the method library is the robust core (folded into #7), but abandons the provocateur half (S2) as a product | rejected |
| R11 | Thousand-muse storm / 10k-variant compost (S24) | Mass unfiltered persona swarm; write-only heap sampled later | Unbounded cost + attention overflow + "never read whole" = dead-artifact risk; the bounded fan-out lives in #7 | rejected |
| R12 | General-purpose creative substrate (S25) | /muse for naming, narrative, life decisions, not just product | Scope-overrun for v1; prove on engineering topics first. Revisit after the engine is proven | rejected |
| R13 | JSON Canvas living surface (S7) | Agent-written `.canvas` as the single spatial view | Contradicts DECISIONS `{#saga-docs-source-model}` + no consumer (dead-wiring). Revisit-when: agent reasons over it OR /ideate ingests it | rejected |
| R14 | Markmap/D2/Kroki diagram layer (S8) | Markdown→mindmap + render gateway | Same rejected-diagram decision; zero repo foundation | rejected |
| R15 | Google satellite ring + NotebookLM (S9/S10/S11) | Drive/Docs corpus + NotebookLM round-trip; unofficial automation | External-dependency spikes (ToS-gray, brittle); opt-in spike not v1 (folded into #2) | rejected |
| R16 | Mandatory per-session integration ritual (S13) | Every session ends by distilling raw→seeds→canvas | Eager structuring is smuggled convergence (re-engages the self-monitor); reshaped to lazy-capture + organize-at-route-exit in #3/#5 | rejected |

Rejection summary: the filter cut on three repeated grounds — re-litigating the settled
rejected-diagram decision (R13/R14/R15, four frames flagged it), dead-wiring or v2-dependency
(R4/R5/R6/R8), and scope/identity overrun (R3/R10/R11/R12). No axis ended with zero survivors
(A1×1, A2×1, A3×2, A4×1, A5×2). The strongest revivables are R4 and R5 — both deferred mechanics, not
flaws — worth reviving once the v1 handoff and method engine exist.

## Co-ideation log

All 28 operator seeds were passed INTO the Phase 2 frame agents to build on / challenge / combine, and
entered the merged pool under the identical critique. Outcomes:

| source | entered | idea / seed | outcome |
|--------|---------|-------------|---------|
| user-seed | Phase 0 | S1 critique-banned zone + parking lot | survived (core of #1 + #3) |
| user-seed | Phase 0 | S2 provocateur + scribe dual role | survived (folded into #1; scribe half informs #3/#5) |
| user-seed | Phase 0 | S3 multi-method library | survived as #7 |
| user-seed | Phase 0 | S4 adaptive orchestration (3 drivers) | survived (folded into #7 as silent-default selection) |
| user-seed | Phase 0 | S5 inchoate-elicitation | survived (folded into #7 as notan/negative-space method) |
| user-seed | Phase 0 | S6 parallel mutation fan-out | survived (folded into #7 as exquisite-corpse blind variation) |
| user-seed | Phase 0 | S7 JSON Canvas | cut → R13 (rejected-diagram decision + dead-wiring) |
| user-seed | Phase 0 | S8 Markmap/D2/Kroki | cut → R14 (rejected-diagram decision) |
| user-seed | Phase 0 | S9/S10/S11 HTML + Google + NotebookLM | cut → R15 (external-dependency spikes, not v1) |
| user-seed | Phase 0 | S12 artifact rubric | survived (folded into #3's typed contract + the quality bar) |
| user-seed | Phase 0 | S13 integration ritual | reshaped → R16 (eager distillation cut; lazy-capture kept in #3/#5) |
| user-seed | Phase 0 | S14 multi-session persistence | survived as #5 |
| user-seed | Phase 0 | S15 replace office-hours | challenged → #4 (don't replace); original → R1 |
| user-seed | Phase 0 | S16 name /muse | settled (operator-chosen; not critiqued) |
| user-seed | Phase 0 | S17 persona panel | folded into #7 (a method) / R11 (swarm version) |
| user-seed | Phase 0 | S18 voice capture | cut → R9 (capability-gated, post-v1) |
| user-seed | Phase 0 | S19 yes-and contract | survived (core enforcement mechanism of #1) |
| user-seed | Phase 0 | S20 silent-scribe mode | folded into #1 / R9 |
| user-seed | Phase 0 | S21 reversed provocation + artifact-first | folded into #6 (genchi genbutsu) + #7 (a method) |
| user-seed | Phase 0 | S22 spaced resurfacing | survived as #5 |
| user-seed | Phase 0 | S23 cross-thread pollination + journal-as-fuel | survived as #6 (+ pollination in #5) |
| user-seed | Phase 0 | S24 mass unfiltered divergence | folded into #7 (bounded) / R11 (unbounded) |
| user-seed | Phase 0 | S25 general-purpose substrate | cut → R12 (scope overrun for v1) |
| user-seed | Phase 0 | S26 machine-readable method registry | survived as #7 |
| user-seed | Phase 0 | S27 wall off convergent family-7 | survived (core of #1's ban-by-absence) |
| user-seed | Phase 0 | S28 honest group-technique simulation | folded into #1/#7 (honesty guard) |
| frame-agent | Phase 2 | structural critique-ban (Pain/Leverage/Constraint frames) | survived as #1 |
| frame-agent | Phase 2 | typed no-new-artifact handoff (Inversion/Leverage/Cross-domain) | survived as #3 |
| frame-agent | Phase 2 | don't-replace-office-hours (Inversion/Assumption/Constraint) | survived as #4 |
| frame-agent | Phase 2 | journal-as-fuel / no blank page (Inversion/Leverage/Cross-domain) | survived as #6 |

## Appendix — full candidate roster (all 6 frames)

Every Phase-2 candidate and its disposition, so nothing generated is lost from the durable record.
"Folded into #N" = merged into that survivor; "→ R#" = a standalone revivable cut. ~50 candidates
consolidated into 7 survivors + 16 revivable cuts.

### Frame 1 — Pain & friction
| id | candidate | disposition |
|----|-----------|-------------|
| F1.1 | Lazy capture, organize at boundary not live | folded into #3/#5 |
| F1.2 | Cold-start re-entry head (5-line "where we left off") | folded into #5 |
| F1.3 | Critique leak → yes-and hard output contract + violation list | survived as #1 (core) |
| F1.4 | Method-selection paralysis → silent default from ~12 hot-set | survived as #7 |
| F1.5 | Dead-on-arrival canvas (producer, no consumer) | → R13 (and #2) |
| F1.6 | Visual-tooling rabbit hole → spine-only default | survived as #2 (and R15) |
| F1.7 | Graduation-cliff airlock (attach basis still critique-free) | survived as #3 |
| F1.8 | Capture-input friction → voice/stream-of-consciousness | → R9 |

### Frame 2 — Inversion / removal / automation
| id | candidate | disposition |
|----|-----------|-------------|
| F2.1 | Blank-page abolition (auto-seed, react not originate) | survived as #6 |
| F2.2 | No save button (every utterance auto-captured) | folded into #1/#3 |
| F2.3 | Kill articulated-basis req (/muse = negative space of /ideate) | folded into #3/#4 |
| F2.4 | Remove operator from divergence (unattended fan-out) | → R6 |
| F2.5 | No session boundary (always-on ambient stream) | → R7 |
| F2.6 | Strip convergent toolbelt (ban-by-absence) | survived as #1 (core) |
| F2.7 | Automate method choice away | survived as #7 |
| F2.8 | No new artifact (append into /ideate inbox) | survived as #3 |
| F2.9 | Don't touch office-hours (sit strictly upstream) | survived as #4 |
| F2.10 | Text-only by design (structuring = smuggled convergence) | survived as #2 |

### Frame 3 — Assumption-breaking & reframing
| id | candidate | disposition |
|----|-----------|-------------|
| F3.1 | Mode toggle, not a command (--divergent flag) | → R2 |
| F3.2 | Flip the arrow (/ideate's cut pile feeds /muse) | → R4 |
| F3.3 | Reframe by mechanism ("gates-off zone", not "imagination") | folded into #1 (rationale) |
| F3.4 | Transcript IS the artifact (drop eager distillation) | reshaped → R16, folded into #3/#5 |
| F3.5 | Visual family S7–S11 is premise-smuggle | survived as #2 |
| F3.6 | Persist a standing prompt, not state | → R8 |
| F3.7 | Make the front-door concept obsolete (merge into /ideate) | → R3 |
| F3.8 | Ban convergence too (muse does zero selection) | folded into #1 (ban-by-absence) |

### Frame 4 — Leverage & compounding
| id | candidate | disposition |
|----|-----------|-------------|
| F4.1 | Journal-as-fuel (mine the existing corpus) | survived as #6 |
| F4.2 | Parking-lot as typed handoff contract | survived as #3 |
| F4.3 | Append-to-top anchored seed log ({#slug} grammar) | survived as #5 (addressability) |
| F4.4 | Cross-thread pollination index | folded into #5 |
| F4.5 | Method registry as versioned data | survived as #7 |
| F4.6 | Spaced-resurfacing hook | survived as #5 |
| F4.7 | Critique-ban as structural invariant → composable primitive | survived as #1 |
| F4.8 | Seed → kept/cut feedback signal (tune methods) | → R5 |

### Frame 5 — Cross-domain analogy
| id | candidate | disposition |
|----|-----------|-------------|
| F5.1 | Genchi genbutsu (riff from the actual artifact) | survived as #6 |
| F5.2 | Sourdough starter (persistence as living levain) | folded into #5 |
| F5.3 | Apophenia engine (collide unrelated seeds) | survived as #7 (mechanic) |
| F5.4 | Notan / negative-space elicitation | survived as #7 (a method) |
| F5.5 | Exquisite-corpse fan-out (manufactured blindness) | survived as #7 (mechanic) |
| F5.6 | Drag-line/tilt energy-timed callback | folded into #5 |
| F5.7 | Mise en place (friction-free capture stations) | folded into #1/#3 |
| F5.8 | Open-water relay / transition-zone handoff | survived as #3 |

### Frame 6 — Constraint-flipping
| id | candidate | disposition |
|----|-----------|-------------|
| F6.1 | Eternal thread (never-closing channel) | → R7 |
| F6.2 | Ash-muse (zero durable storage) | folded into #3 (minimal-artifact tension) |
| F6.3 | Thousand-muse storm (1000 persona-agents) | → R11 |
| F6.4 | Silent muse (human never types) | folded into #6, → R6 |
| F6.5 | No-AI provocation deck | → R10 |
| F6.6 | 10,000-variant compost heap | → R11 |
| F6.7 | Inverted gate (anti-office-hours, frame-dissolving) | survived as #4 |
| F6.8 | One-way mirror (no self-reference within a riff) | survived as #1 (core) |
