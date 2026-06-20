---
date: 2026-06-19
topic: global-engineering-journal
focus: Elevate the per-repo engineering journal to a global (workspace/machine/cross-machine) level
scope: broad
repo: infiquetra-claude-plugins
maturity: idea-ready
---

# Ideation: Global Engineering Journal

Run-id `3d0b82f0`. Cross-cutting / workspace-global run (cwd was the non-git workspace root
`~/workspace/infiquetra`, not a single repo); saved here because most actionable survivors are saga
changes. 6-frame fan-out + 2 grounding agents (local reality + external prior art).

## Core realization

You already own nearly every primitive a global journal needs — they're just unused. The gap is three
missing **verbs**, not a missing tool or a RAG system:

- **promote** — lift cross-repo learnings out of their silos,
- **recall** — find them from anywhere,
- **carry** — survive across machines.

And a "global journal" is really **three shelf-lives**: durable LEARNINGS/DECISIONS (globalize freely),
volatile QUEUED (push to Todoist, don't pay sync tax), and a tiny always-loaded hot set. Build the
right home for each, and make the global layer **derived, never hand-maintained** (a hand-kept global
file rots — see `tasks/todo.md`, prescribed in CLAUDE.md and used by 0/31 repos).

**Terminology.** The journal's `Generalizable rule` subheader captures a distilled **learning** —
information to guide a future decision, not a law to enforce. The global layer is a body of *learnings*;
only the rare entry (e.g. Validation-Discipline) hardens into a directive. This reframe reinforces the
no-RAG call: you're surfacing guidance to inform a decision, not enforcing an authoritative index, so
grep is enough.

## Grounding Context

**Repo / reality:** 31 repos carry `docs/engineering-journal/` (LEARNINGS/DECISIONS/QUEUED/ARCHIVE +
narratives/), each a silo with zero rollup; **785 `**Generalizable rule.**` lines already exist** across
them (≈700 real entries after filtering template/meta lines — these are your distilled **learnings**, one
per LEARNINGS entry; stable, greppable marker). The saga `/retro` skill already pure-appends learnings/decisions/queued/
archive into a repo's journal unattended — but is single-repo scoped. Machine-level hooks already exist
and are unused: global `~/.claude/CLAUDE.md` (defines the journal rules, loads every session) and the
Claude Code auto-memory dir `~/.claude/projects/-Users-jefcox/memory/` (EXISTS but EMPTY, MEMORY.md
index, one-fact-per-file). `tasks/todo.md` used by 0/31 repos; home-lab QUEUED.md is 452KB. No
cross-machine sync; the workspace root is not a git repo; dotfiles tracks `.claude/` config as a template
baseline only.

**Context-libraries:** `infiquetra-context-library` — canonical org-wide standards/decisions location
with its own journal; the natural promotion target for learnings that recur across repos.

**External prior art:** Basic Memory (basicmachines-co) and simonw/til are the closest design analogs —
file-first markdown, no vector DB. RAG-over-notes fails on retrieval (staleness/drift/re-index tax),
and Anthropic's own stance is that agentic grep beats a vector index for journal-sized markdown
(Claude Code ships on grep, no vectors). Todoist exposes an official hosted MCP (`ai.todoist.net/mcp`)
that drops into Claude Code. Flags: "openbrain" is most likely the AI-2027 fictional lab (or tiny
GitHub projects), not a tool to bet on; Cursor "Memories" was removed (don't model on it); Claude Code
native auto-memory overlaps the "agent-maintained global journal" goal — reconcile, don't duplicate.

## Topic Axes

- A — Placement & structure (where the global layer lives + how organized)
- B — Capture & cross-repo promotion (how findings bubble up from 31 silos)
- C — Retrieval & recall (how knowledge surfaces when relevant)
- D — Cross-machine sync & durability
- E — Backlog/queue integration + Todoist

## Ranked Survivors

### 1. Derived global learnings rollup — harvest the ~700 you already wrote

One generated `GLOBAL_LEARNINGS.md`, built by harvesting the distilled learnings (the `Generalizable
rule` lines) already in your journals — never hand-edited, rebuildable on command.

A script greps the stable `**Generalizable rule.**` marker across all 33 journals (785 hits today, ≈700
real entries), emits one workspace-level file with each learning prefixed by its source `repo/file:line`,
and you re-run it to refresh. Source of truth stays in the repos; the global file is a disposable
projection, so it can't drift the way a hand-kept file does — think `make journal`, not a document.

These are the highest-value learnings you have (per CLAUDE.md, the `Generalizable rule` line is the
single highest-value field), they already exist, and they're already tagged — so this is direct evidence
at near-zero build cost with same-day payoff; it also defuses seed S1 (a workspace file one level up is
right, but only if generated). Downsides: the marker has format variants (602 canonical, plus
heading/punctuation variants and some template-header leakage), so the harvest needs light normalization,
not a dumb `cat`; and it's a snapshot — without #2 feeding it, it goes stale.

| field | value |
|-------|-------|
| basis | `direct:` 785 `**Generalizable rule.**` lines confirmed via grep across the journals (≈700 real learnings); tasks/todo.md at 0/31 adoption |
| confidence | 88 |
| complexity | Low |
| axis | A — placement & structure |
| status | Unexplored |

### 2. Teach `/retro` to promote upward

Add one "promote cross-repo" step to the `/retro` skill that already auto-files learnings, so future
generalizable findings flow up to the rollup — and to `infiquetra-context-library` when they recur.

`/retro` already pure-appends learnings/decisions with no confirmation; it's just single-repo blind.
Give it a final classifier: when an entry carries a `Generalizable rule` line, also append it to the
global rollup with provenance; when the same learning independently appears in ≥2–3 repos, flag it for
promotion to an org standard. A dedup/threshold guard keeps the global layer from becoming a junk drawer.

This reuses the one piece of machinery that already runs unattended at the richest possible moment (when
the learning is born), so capture costs nothing new — it's the compounding engine that keeps #1 fresh
forever. Downsides: cross-repo classification needs judgment (false promotes add noise; misses stay
siloed) and it edits a shared lifecycle skill, so it wants care.

| field | value |
|-------|-------|
| basis | `direct:` /retro confirmed to auto-append, single-repo scoped; context-library is the canonical org-standard target |
| confidence | 84 |
| complexity | Med |
| axis | B — capture & cross-repo promotion |
| status | Unexplored |

### 3. `/recall` — agentic grep across all journals, not RAG

A thin `/recall <topic>` skill that globs and greps every repo's journal and returns ranked hits with
provenance — cross-repo recall today, no index to build or keep fresh.

It fans `grep` across `*/docs/engineering-journal/*.md`, pulls matching entries plus their nearby
`Mechanism` / `Generalizable rule` lines, and returns them with `repo/file:line`. A saved "last 7 days
across all repos" variant gives a standup-style digest on demand. This is the direct rebuttal to seed S3.

The grounding is decisive — RAG-over-notes fails on retrieval, while agentic grep beats a vector index
for journal-sized markdown (Anthropic's own design choice for Claude Code; simonw/til proves structured
markdown + full-text search beats vectors at this scale). Downsides: grep is literal — it misses synonyms
a vector search might catch, so it leans on consistent vocabulary; a much larger corpus would want a
til-style SQLite FTS index (still no vectors).

| field | value |
|-------|-------|
| basis | `external:` Anthropic "just-in-time" agentic retrieval (Claude Code ships on grep); simonw/til |
| confidence | 85 |
| complexity | Low |
| axis | C — retrieval & recall |
| status | Unexplored |

### 4. Fill the empty auto-memory dir — the always-surfaced learnings

Promote only your top cross-repo learnings into Claude Code's native auto-memory dir (one-fact-per-file),
which the harness injects into every session — recall with zero retrieval step.

`~/.claude/projects/-Users-jefcox/memory/` already exists, is indexed by MEMORY.md, and is completely
empty — an unused machine-wide primitive that loads into every session's context for free. Feed it the
handful of learnings worth seeing in every session — mostly guidance, with the rare genuine directive
(e.g. the Validation-Discipline rule) as the special case — curated ruthlessly to a small token budget
and earned by recurrence. The full rollup (#1) stays the searchable cold tier; this is the hot tier.

This is seed S2 answered honestly — the "memory tool to adopt" is the one already wired in and at zero
utilization, not a new dependency; because it's push (injected) not pull (queried), it sidesteps the
retrieval problem RAG fails at. Downsides: context budget is scarce, so it only works kept tiny; it
overlaps Claude Code's own evolving memory feature, so reconcile rather than fight it.

| field | value |
|-------|-------|
| basis | `direct:` auto-memory dir confirmed empty; one-fact-per-file taxonomy; CLAUDE.md's Validation-Discipline is exactly such a learning that hardened into a directive |
| confidence | 80 |
| complexity | Med |
| axis | A — placement & structure (hot/cold tiering) |
| status | Unexplored |

### 5. A git-backed global journal repo for cross-machine durability

Put the global layer in one small git repo (or `infiquetra-context-library`), so cross-machine sync,
durability, and provenance come from git for free.

The workspace root isn't a git repo and nothing syncs `.claude` across machines today, so a
workspace-level file alone dies on your other boxes. A dedicated `infiquetra-journal` repo holds the
generated rollup + the seeded memory + any index; symlink the memory dir into it, and `git pull` on a
new machine is the entire sync story. Append-only markdown is the ideal git payload.

Cross-machine is the one part of the ask with genuinely no current answer, and git already solves
replication, durability, offline, and history — a hosted memory DB would be strictly worse; promotion
becomes an auditable commit. Downsides: concurrent edits on two machines mean occasional merge conflicts
(mitigated by append-only + per-repo sections), and it's one more repo to remember to push.

| field | value |
|-------|-------|
| basis | `direct:` workspace root not a git repo, no cross-machine sync, dotfiles only tracks config; `external:` Basic Memory / til prove markdown-in-git needs no server |
| confidence | 78 |
| complexity | Med |
| axis | D — cross-machine sync & durability |
| status | Unexplored |

### 6. Close the Todoist loop and retire the dead `todo.md`

Make Todoist bidirectional via its official MCP — push P0/P1 QUEUED items with a backlink, read the
queue back at session start, auto-complete on ship — and formally kill `tasks/todo.md`.

The official Doist MCP (hosted at `ai.todoist.net/mcp`) drops into Claude Code, so `/retro` can push
selected queued items out, sessions can pull "open P1s across all repos" at the start of work, and moving
a QUEUED item to ARCHIVE as SHIPPED auto-closes its task. Separately, retire `tasks/todo.md` from
CLAUDE.md — prescribed, used by 0/31 repos, a zero-adoption directive that erodes trust in the rest of
the file.

A backlog only has value if it's read, so meeting your attention where it already is (Todoist, on your
phone) plus a return path converts the graveyard into a system; pick one source of truth (QUEUED is the
record, Todoist the live surface) so the two can't drift. Downsides: bidirectional sync has real edge
cases (dup detection, conflicting completes) and is the most moving-parts idea here; it only pays off if
you actually keep Todoist as your daily surface.

| field | value |
|-------|-------|
| basis | `direct:` seed S4; Todoist hosted MCP works in Claude Code; tasks/todo.md at 0/31; CLAUDE.md "QUEUED ships → ARCHIVE SHIPPED" |
| confidence | 74 |
| complexity | High |
| axis | E — backlog/queue integration |
| status | Unexplored |

## Did not survive (revivable)

Explicit rejection is the quality mechanism. Cut ideas keep stable ids so they can be revived (which
re-enters the Phase 3 filter with new evidence).

| id | title | summary | reason | status |
|----|-------|---------|--------|--------|
| R1 | Adopt a dedicated memory tool | Bring in Basic Memory / mem0 / Letta / Zep | Heavier than needed — mem0/Letta/Zep want a vector or graph DB; native auto-memory + grep dominate at journal scale | rejected |
| R2 | Build a vector RAG (seed S3, literal) | Embed the journals, retrieve by similarity | Fails on retrieval + carries an embed/re-index tax; dominated by agentic grep for journal-sized markdown | rejected |
| R3 | Case-law citation graph | `Cites:` / `Overruled-by:` links + a "good law" staleness check | Novel staleness fix but higher complexity; better as a later layer on #1 once the rollup exists | rejected |
| R4 | Git-hook promotion trigger | A post-commit hook scrapes new learning lines instead of `/retro` | Deterministic but fragile to install across 31 repos and judgment-free; duplicates #2's path | rejected |
| R5 | Global-first (repos are views) | One global store; per-repo journals become projections of it | Elegant but a massive migration against the grain of 33 silos and `/retro`; #1 gets most of it cheaply | rejected |
| R6 | Dedicated scheduled distiller | A CALL-style consolidation cron as its own job | Valuable at volume but premature; folded into #2's promotion cadence for now | rejected |

Axis coverage: A×2, B, C, D, E — no zero-survivor axis. ~49 raw candidates across 6 frames collapsed
hard; most cuts were duplicates folded into the survivor that stated the move best (memory-consolidation
/ LSM-compaction / CALL → #2; generated-index / event-sourcing / newsroom-morgue → #1; zero-tooling /
read-10x digest → #3; dotfiles-carrier / git-submodule → #5; andon-cord / SRE-runbook-split → #6).

## Co-ideation log

| source | entered | idea / seed | outcome |
|--------|---------|-------------|---------|
| user-seed | Phase 0 | S1 — workspace journal + CLAUDE.md one level up | reshaped; survived as #1 (generated form) + #5 (git home). Challenged: hand-kept global files rot (tasks/todo.md 0/31) |
| user-seed | Phase 0 | S2 — adopt an existing memory tool (openbrain / memory apps) | redirected to #4 (native auto-memory); tool-adoption form cut → R1 |
| user-seed | Phase 0 | S3 — a RAG system | challenged by grounding; answered by #3 (agentic grep); literal RAG cut → R2 |
| user-seed | Phase 0 | S4 — Todoist, write-only queue, ignored | built on; survived as #6 (bidirectional + read-back) |
| frame-agent | Phase 2 (leverage) | learnings harvest (785 lines) | survived as #1 |
| frame-agent | Phase 2 (inversion / assumption / leverage) | extend /retro append to global | survived as #2 |
| frame-agent | Phase 2 (pain / inversion / assumption) | grep-not-RAG /recall | survived as #3 |
| frame-agent | Phase 2 (pain / leverage / assumption) | fill empty auto-memory dir | survived as #4 |
| frame-agent | Phase 2 (analogy / constraint / inversion) | git-backed cross-machine journal | survived as #5 |
| frame-agent | Phase 2 (analogy / constraint) | citation-graph, global-first, distiller pass | cut → R3, R5, R6 |
