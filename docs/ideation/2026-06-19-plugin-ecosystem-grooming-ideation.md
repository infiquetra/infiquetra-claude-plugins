---
date: 2026-06-19
updated: 2026-06-19 (operator dispositions folded in — Phase 6)
topic: plugin-ecosystem-grooming
focus: groom the plugin portfolio (cut/keep/consolidate/extract), build-vs-adopt, and the agent/model/context economy
scope: broad
repo: infiquetra-claude-plugins
maturity: idea-ready
---

# Ideation: Plugin Ecosystem Grooming & Agent/Model/Context Economy

## Grounding Context

**Repo:** A Claude Code plugin marketplace monorepo, 17 plugins (marketplace metadata reads 2.4.0 in memory / 2.1.0 in-file — itself a drift signal). Two plugin types: skills-based (markdown) and CLI-based (Python). `saga` is the dominant plugin (the engineering lifecycle spine — 17 skills, 18 commands). No root `STRATEGY.md`. Stale README (lists 11 of 17). Incoherent versioning (0.1.1 → 3.0.0).

**Binding journal decisions:** (1) `agents/*.md` are NOT auto-loaded — they are subagent definitions invokable only via the Agent tool; the canonical convention is **no `agents/` dir → use generic agents**, and custom-agent dirs were REJECTED twice (qa-engine + resume-engine rebuilds, for saga's internal fan-out). (2) Model/effort tiering: ZERO journal coverage (Agent tool + Workflow `agent()` support per-call model/effort). (3) "No longer needed with current LLMs": ZERO coverage. (4) Plugin release = code + `plugin.json` + marketplace + changelog + drift tests in SAME PR; marketplace-drift shipped TWICE; `#marketplace-ci-guard` is P1.

**Existing tooling that overlaps these ideas (verified 2026-06-19):**
- **Langfuse observability plugin is installed** (`langfuse-observability` v1.0.0, since 2026-06-18). It traces every Claude Code session — *tool calls, token usage, and a `skill:<name>` tag per turn* (`CC_LANGFUSE_SKILL_TAGS` on by default) — to the operator's Langfuse instance via Stop/SessionEnd hooks. So per-skill usage AND token cost are already captured (≈1 day of history so far; transcripts hold the back-catalog). This makes #6 a *report-over-existing-telemetry* problem, not a new ledger.
- **/retro (saga's improve stage) already** mines session transcripts (Phase 1.5), runs **new-skill / plugin detection** (Phase 5a — "repeated friction a new skill/plugin would remove"), writes a retro doc (Phase 3), and pointedly uses **generic agents, no `agents/` dir** — which independently validates #3's roster collapse. So the "review sessions → suggest plugins" half of #3/#10 already exists.

**Measured usage (the seed-1 transcript scan):** Full 1.3 GB / 1,833-file `~/.claude` corpus, ~all <30 days old.
- Fire: `saga` 16,502 · `team-execution` 2,339 · `redis-channel` 152 · `home-lab-ops` ~60 · `mission-control` ~48 · `unifi` 11. External: `compound-engineering` 2,578 + `superpowers` 706 (saga's upstream sources), `agy` 30 + `codex` 22 (operator already delegates outward), `commit-commands` 22, `discord` 11.
- ZERO attributed fires: `slack`, `splunk`, `pagerduty`, `identity-toolkit`, `sdk-lifecycle`, `todoist-manager`, `marketplace-lister`, `python-toolkit`, `test-suite`, `docs-generator`, `deploy`.
- Subagents: generic `Explore` 362 + `general-purpose` 364 + `Plan` 15 dominate; all 9 bespoke domain agents = ZERO ad-hoc fires.
- Operator hand-manages the economy: `/effort` ×113, `/compact` ×48, `/model` ×28, `/context` ×17, `/fast` ×3.

**Context-libraries:** None consulted (repo-bound topic). **Prior art folded in:** `2026-05-30-delegate-agent-plugin-ideation.md` (largely shipped via `agy`/`codex`).

## Topic Axes

- A. Portfolio grooming — keep / cut / consolidate / extract.
- B. Capability gaps — build new vs adopt existing (buy-vs-build).
- C. Agent triggering & roster — why bespoke agents don't fire; what roster earns its place.
- D. Execution economy — model-tiering + context/cache cost.
- E. Ecosystem hygiene & meta — drift guards, versioning, sync, maintenance automation, self-knowledge.

## Operator dispositions & next steps (Phase 6)

The operator reviewed all 11 survivors. Dispositions:

| # | idea | axis | disposition |
|---|------|:---:|---|
| 1 | Cause-classified grooming pass | A | **CONFIRMED** — decisive cut: 17 → 7 keep, 9 cut, 1 relocate (table in card #1) |
| 2 | Mechanical-ops offload | D | **REFRAME** — prefer well-defined *triggered skills*, not a rule → Track 1 |
| 3 | Collapse the agent roster | C | **CONFIRMED** — collapse; keep only justified cheap-tier agents; enumerate them in Track 1. Session-review→suggest already in /retro |
| 4 | Generate registry + README from `plugin.json` | E | **CONFIRMED** |
| 5 | Per-task model/effort tiering | D | **CONFIRMED** — operator has no concrete shape yet; explore mechanism in Track 1 |
| 6 | Usage report (was: ledger) | E | **REFRAME** — Langfuse already captures usage+cost; build an on-demand report, not a ledger |
| 7 | Plugin-grooming capability (was: buy-vs-build gate) | B | **REFRAME** — a plugin that *grooms plugins* and always searches existing marketplaces (pre-seeded locations) → Track 2 |
| 8 | Journal-aware substrate | B | **CONFIRMED** |
| 9 | Prune LLM-obsolete guards | A | **CONFIRMED** |
| 10 | After-action report in improve stage | E | **CONFIRMED** — extend /retro (already writes a retro doc) with a defined AAR format → Track 2 |
| — | (was #11) Codex/Antigravity backends | B | **PARKED** → moved to revivable cut R6 |

**Two follow-on generative tracks** emerge from the dispositions:

**Track 1 — Net-new skills & cheap-tier agents from how I actually work** (folds #2 + #3-roster + #5). A new `/ideate` run whose focus is *well-triggered skills + justified cheap-tier agents*, grounded in **transcript + commit work-pattern mining** (recurring git sequences, bash batches, review/debug loops that aren't yet a skill) — a heavier grounding than this run's usage-counting. Ideation, not brainstorm, because the goal is to *generate a list* from patterns. Model-tiering (#5) rides along: each candidate declares a recommended tier; the cheap git-ops offloader is the worked example. Separable sub-task: a tier policy for *existing* saga commands.

**Track 2 — Self-grooming improve stage** (folds #6 + #7 + #10, minus what /retro already does). /retro already mines sessions, detects new-skill friction, and writes a retro doc. The genuinely-new piece is a periodic, corpus-wide **portfolio-grooming capability** that (a) reports usage+cost from Langfuse/transcripts, (b) ALWAYS searches existing marketplaces before suggesting a build, (c) flags dead/orphan plugins, (d) proposes new skills — i.e. *this session, productized*. Brainstorm (shape one capability + decide new `/groom` skill vs. a portfolio mode of /retro), not ideation. #10 = add a defined after-action-report section to /retro's doc.

**Immediate, shovel-ready:** execute the #1 cut, plus #4 (registry generator) and #9 (obsolete-guard sweep) and #8 (already P2-queued).

## Ranked Survivors

### 1. Cause-classified grooming pass — delete/archive/extract, not a blunt purge

Classify each zero-fire plugin by *why* it's silent, because "zero usage" has several causes and only one justifies a hard delete.

The operator settled the verdicts decisively (no bash-path measurement needed — "if I need that later I'll build something new"): the marketplace goes from 17 to **7 keep, 9 cut, 1 relocate**.

**Disposition:** CONFIRMED with these verdicts.

| plugin | verdict | note |
|---|---|---|
| saga, team-execution, mission-control, redis-channel, home-lab-ops, unifi | **KEEP** | all fire |
| deploy | **KEEP** | works with saga (not probation) |
| slack, pagerduty, splunk | **CUT** | 0 fires; service wrappers |
| identity-toolkit, sdk-lifecycle | **CUT** | 0 fires; knowledge-only; LLMs subsume them |
| python-toolkit, test-suite, docs-generator | **CUT** | 0 fires; rebuild later if needed |
| todoist-manager | **CUT** | move to the Todoist MCP (with deferred MCP tool-loading, the context-cost argument for a CLI plugin is weak; flag only if a real cost/efficiency gap shows up) |
| marketplace-lister | **RELOCATE** | move to `infiquetra-hermes-plugins` — it's intended for a hermes agent |

| field | value |
|-------|-------|
| basis | direct: zero-attribution corpus data + operator verdicts (US1/US5/US6) |
| confidence | 92 |
| complexity | Low-Med |
| axis | A |
| status | Explored |

### 2. Mechanical-ops offload to a cheap throwaway sub-session

Make it a rule that the high-context main session never runs `git commit`/`push`/`PR-open`/`format`/`lint` itself — those ship to a fresh Haiku-tier sub-session that returns only the result.

**Disposition:** REFRAME → the operator prefers this expressed as *well-defined, well-triggered skills/plugins* rather than a loose "rule." The specific list of such mechanical-ops skills/agents (git-ops offloader, batch-bash, etc.) is generated in **Track 1**, grounded in transcript work-patterns. The savings only land if the sub-agent runs a cheaper model AND the handoff is tight (a subagent that inherits the default model and re-reads the repo moves cost, it doesn't remove it).

| field | value |
|-------|-------|
| basis | direct: US2 + US3 + /compact ×48 + /context ×17 + agy/codex already offload |
| confidence | 85 |
| complexity | Med |
| axis | D |
| status | Explored → routed to Track 1 |

### 3. Collapse the agent roster — delete the dead `agents/` dirs, keep only justified cheap-tier agents

Delete the 9 bespoke domain agent files (zero fires, domain mismatch, all on the default model), and allow an agent file *only* when it justifies a non-default model/effort/tool-scope.

The positive reframe (from the conversation): an agent earns its file when it pins a **cheaper tier or narrower tools** — the commit/git-ops offloader is the canonical *keep*; `pagerduty-ops`/`digital-identity-architect` are the canonical *cut* (good prose, but the work never happens and they inherit the default model). /retro's own design ("no `agents/` dir → generic agents") validates this.

**Disposition:** CONFIRMED — collapse. The list of *justified* agents to build is generated in **Track 1**. Note: the "review sessions → suggest new plugins" idea the operator floated already exists as /retro Phase 5a.

| field | value |
|-------|-------|
| basis | direct: 9 bespoke agents @ 0 ad-hoc fires + "NO agents/ dir" convention + /retro uses generic agents |
| confidence | 90 |
| complexity | Low |
| axis | C |
| status | Explored → roster cut now; new agents → Track 1 |

### 4. Generate `marketplace.json` + README from `plugin.json` (single source of truth)

Generate the marketplace array and README plugin table from per-plugin `plugin.json`, and let the queued P1 CI guard assert they match.

**Disposition:** CONFIRMED. Shovel-ready; closes the drift that shipped twice. The 17→7 cut (card #1) should land *with* this so the generator's first output is the groomed set.

| field | value |
|-------|-------|
| basis | direct: README 11/17 stale + drift shipped twice + #marketplace-ci-guard (P1) + memory editing-guard |
| confidence | 86 |
| complexity | Low-Med |
| axis | E |
| status | Explored |

### 5. Per-task model/effort tiering as declared saga policy

Annotate each saga command with a recommended tier so dispatch picks the model instead of the operator typing `/model`/`/effort` ~140 times — and express "cheap-and-wide" (many Haiku Explore + one expensive synthesis), not just "smart-and-one."

**Disposition:** CONFIRMED ("love this if it can actually happen") — operator has no concrete shape yet. Explore the mechanism in **Track 1** (each candidate skill/agent declares a tier; the offloader is the worked example). The policy layer for *existing* saga commands is a separable design task.

| field | value |
|-------|-------|
| basis | direct: US4 + /effort ×113 + /model ×28 + "model tiering: ZERO journal coverage" |
| confidence | 80 |
| complexity | Med |
| axis | D |
| status | Explored → routed to Track 1 |

### 6. Usage report over existing telemetry (was: build a usage ledger)

Build an on-demand report that answers "which plugins/skills fire, at what token cost, what's gone dark" — reading the telemetry that **already exists** rather than instrumenting a new ledger.

**Disposition:** REFRAME. The Langfuse plugin already captures tool calls + token usage + `skill:<name>` tags; transcripts hold the back-catalog. So this is a report/query layer (on-demand, with purpose), most naturally a piece of **Track 2** (the grooming capability) or a /retro mode — not a new ledger. Buy-vs-build win.

| field | value |
|-------|-------|
| basis | direct: Langfuse plugin traces tool calls + tokens + skill tags (verified) + transcript attribution fields |
| confidence | 80 |
| complexity | Low-Med |
| axis | E |
| status | Explored → routed to Track 2 |

### 7. A plugin that grooms plugins (was: buy-vs-build gate)

Productize *this very session* as a repeatable saga capability: a grooming pass that always searches existing marketplaces (pre-seeded locations) for prior art before suggesting any build, reports usage, and flags dead/orphan plugins.

**Disposition:** REFRAME — the operator rejected the bare "buy-vs-build gate" (too late / risks building a plugin that already exists) in favor of this. The existing-plugin search is the load-bearing feature; pre-seed it with the known marketplaces (official, awesome-claude-code-plugins, claude-code-plugins, langfuse, infiquetra's own). Shape in **Track 2** (new `/groom` skill vs. a portfolio mode of /retro).

| field | value |
|-------|-------|
| basis | direct: US5 + agy/codex/CE/superpowers out-fire local plugins + operator reframe |
| confidence | 78 |
| complexity | Med |
| axis | B |
| status | Explored → routed to Track 2 |

### 8. Journal-aware lifecycle substrate — the journal plugin, sharpened

Promote `#engineering-journal-plugin` from "template-copier" to a substrate whose read side is a first-class saga primitive: lifecycle commands query prior LEARNINGS/DECISIONS before they re-derive a lesson.

**Disposition:** CONFIRMED ("forgot we had this queued"). Direct evidence it leaks value today: the same provenance trap fired three times across builds because nothing forced a pre-build journal read.

| field | value |
|-------|-------|
| basis | direct: #engineering-journal-plugin (P2) + provenance trap fired 3× + 2 manual adopters |
| confidence | 75 |
| complexity | Med-High |
| axis | B |
| status | Explored |

### 9. Prune LLM-obsolete guards/scaffolding — the seed-5 sweep

Pass over saga's skills asking of each guard "does a current frontier model still misbehave without this?" and delete what no longer changes behavior.

**Disposition:** CONFIRMED. Greenfield (zero journal coverage), and saga's 16,502 fires amplify every obsolete guard. Careful per-guard end-to-end check before each removal — removing a still-load-bearing guard is a silent regression.

| field | value |
|-------|-------|
| basis | direct: US6 + "no longer needed with current LLMs: ZERO coverage" + saga 16,502 fires |
| confidence | 72 |
| complexity | Med |
| axis | A |
| status | Explored |

### 10. After-action report in saga's improve stage

The operator already holds the concept of an after-action report (AAR) for the "improve" stage. /retro is that stage and already writes a retro doc, so this is an enhancement: a defined AAR format/section, optionally fed by the #10/#6 telemetry mining over the saga tick-chain (16,502 fires) and Langfuse.

**Disposition:** CONFIRMED — build the AAR into /retro (Track 2). The all-ticks reader already exists, so the marginal cost is the report format + the analytics pass.

| field | value |
|-------|-------|
| basis | direct: operator's AAR concept + /retro writes a retro doc + saga 16,502 fires + all-ticks reader exists |
| confidence | 74 |
| complexity | Med |
| axis | E |
| status | Explored → routed to Track 2 |

## Did not survive (revivable)

| id | title | summary | reason | status |
|----|-------|---------|--------|--------|
| R1 | Split saga into spine + phase packs | Thin router + on-demand phase packs | Premise that all 18 commands load per-turn is unverified (skills load on invocation); contradicts the unify decision | rejected |
| R2 | Saga as 100 micro-plugins | Explode saga into single-command plugins | Subject-distorting; only kernel (per-command fire audit) folded into Track 2 telemetry | rejected |
| R3 | Context-watchdog / auto-compact hook | Hook watches context fill and auto-offloads | Too speculative; harness already auto-compacts; frugal-defaults kernel folded into #2/#5 | rejected |
| R4 | Wide-cheap-swarm vs one expensive agent | Many Haiku agents + one synthesis pass | A tactic, not a deliverable — folded into #5 ("cheap-and-wide") | rejected |
| R5 | Bundle dead plugins into one dormant `ops-integrations` | Keep slack/pagerduty/splunk idle-bundled | Dormant code still carries cost; git history is the archive. Revive if on-call need emerges | rejected |
| R6 | Codex/Antigravity as saga execution backends | Fold agy/codex into saga operator-choice as backends | Operator unsure + lowest score; prior art largely shipped (agy/codex work standalone). Revive if ad-hoc cross-model delegation becomes a pain | rejected |

No axis ended with zero survivors. Axis C is intentionally served by one comprehensive idea (#3) — the data says the roster should collapse, not multiply.

## Co-ideation log

| source | entered | idea / seed | outcome |
|--------|---------|-------------|---------|
| user-seed | Phase 0 | US1: remove slack/identity-toolkit/pagerduty/splunk/sdk-lifecycle | survived → #1; expanded by operator to a 17→7 cut |
| user-seed | Phase 0 | US2: offload "commit at 90% context" to a sub-session | survived → #2; reframed to triggered skills (Track 1) |
| user-seed | Phase 0 | US3: an agent that batches bash/git-ops | survived, fused into #2 / Track 1 |
| user-seed | Phase 0 | US4: agents that pick a different model | survived → #5; folded into Track 1 |
| user-seed | Phase 0 | US5: don't build what existing tools cover | survived → #7; reframed to a grooming capability (Track 2) |
| user-seed | Phase 0 | US6: prune capabilities/guards obsolete under current LLMs | survived → #9 |
| frame-agent | Phase 2 | Collapse the agent roster / generate registry / usage ledger / journal substrate / telemetry / codex backends | survived → #3 / #4 / #6 / #8 / #10 / R6 |
| operator | Phase 6 | deploy is a must-keep (works with saga) | applied to #1 (KEEP, not probation) |
| operator | Phase 6 | marketplace-lister → infiquetra-hermes-plugins | applied to #1 (RELOCATE) |
| operator | Phase 6 | todoist-manager → use the MCP | applied to #1 (CUT) |
| operator | Phase 6 | cut the measure/decide trio outright | applied to #1 (python-toolkit/test-suite/docs-generator CUT) |
| operator | Phase 6 | #2/#3/#5 should become a list of well-triggered skills/agents from work-patterns | created Track 1 |
| operator | Phase 6 | #6 likely covered by Langfuse; #7 → a plugin that grooms plugins; #10 → AAR in improve stage | created Track 2; reframed #6/#7/#10 |
| operator | Phase 6 | #11 — not sure | parked → R6 |
