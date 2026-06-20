---
date: 2026-06-19
topic: plugin-ecosystem-grooming
focus: groom the plugin portfolio (cut/keep/consolidate/extract), build-vs-adopt, and the agent/model/context economy
scope: broad
repo: infiquetra-claude-plugins
maturity: idea-ready
---

# Ideation: Plugin Ecosystem Grooming & Agent/Model/Context Economy

## Grounding Context

**Repo:** A Claude Code plugin marketplace monorepo, 17 plugins (marketplace metadata reads 2.4.0 in memory / 2.1.0 in-file — itself a drift signal). Two plugin types: skills-based (markdown) and CLI-based (Python). Quality bar: py3.12, ruff (100-char), mypy, bandit, 80% coverage, uv. `saga` is the dominant plugin (the engineering lifecycle spine — 17 skills, 18 commands). No root `STRATEGY.md`. Stale README (lists 11 of 17 plugins). Incoherent versioning (0.1.1 → 3.0.0, no cadence).

**Binding journal decisions that shaped this run:** (1) `agents/*.md` are NOT auto-loaded — they are subagent definitions invokable only via the Agent tool; the canonical plugin convention is **no `agents/` dir → use generic agents**, and custom-agent dirs were explicitly REJECTED twice (`#cc-channels-surface-split`, `#resume-port-source-verified-true`, `#qa-engine-rebuild`, `#resume-engine-rebuild`). (2) Model/effort tiering has ZERO journal coverage (greenfield; the Agent tool + Workflow `agent()` both support per-call model/effort). (3) "No longer needed with current LLMs" has ZERO journal coverage (seed 5 is unexplored). (4) Context learnings: file-mediated extraction, skim-not-read, optimize docs for LLM+human legibility not absent parsers, fan-out budget-exhaustion failure mode. (5) Plugin release = code + `plugin.json` + marketplace entry + changelog + drift tests in the SAME PR; the marketplace-drift bug shipped TWICE; `#marketplace-ci-guard` is P1-queued. (6) `team-execution` + `deploy` were deliberately NOT vendored into `saga` (real boundaries); the engine-merge campaign deliberately UNIFIED saga into one plugin.

**Measured usage (the seed-1 transcript scan):** Full 1.3 GB / 1,833-file `~/.claude` corpus across 40 projects; ~all <30 days old, so this is current behavior.
- Plugins that fire: `saga` 16,502 · `team-execution` 2,339 · `redis-channel` 152 · `home-lab-ops` ~60 · `mission-control` ~48 · `unifi` 11. External installed plugins also used: `compound-engineering` 2,578 + `superpowers` 706 (saga's upstream port sources), `agy` 30 + `codex` 22 (operator already delegates to Antigravity/Codex), `commit-commands` 22, `discord` 11.
- ZERO attributed skill/command/MCP/subagent fires in the entire corpus: `slack`, `splunk`, `pagerduty`, `identity-toolkit`, `sdk-lifecycle`, `todoist-manager`, `marketplace-lister`, `python-toolkit`, `test-suite`, `docs-generator`, `deploy`.
- Subagents: generic `Explore` 362 + `general-purpose` 364 + `Plan` 15 dominate. Every one of the 9 bespoke domain agents (digital-identity-architect, pagerduty-ops, marketplace-lister, todoist-manager, homelab-sre, unifi-network-ops, release-orchestrator, sdlc-operator, redis-channel-coach) = ZERO ad-hoc invocations.
- Operator hand-manages the economy: `/effort` ×113, `/compact` ×48, `/model` ×28, `/context` ×17, `/fast` ×3 (~280 manual interventions).

Caveat: "zero attributed usage" = zero skill/command/MCP/subagent fires. A plugin invoked purely via raw `bash` would not attribute, which is why survivor #1 measures the bash path for `python-toolkit`/`test-suite`/`docs-generator` before any verdict.

**Context-libraries:** None consulted — the topic is bound to this repo's own plugins/agents.

**Prior art folded in (not regenerated):** `docs/ideation/2026-05-30-delegate-agent-plugin-ideation.md` (the provider-neutral delegation ideation — largely shipped via the `agy` + `codex` plugins). This run starts fresh on the broader grooming question and treats that doc as prior art behind survivor #11.

## Topic Axes

- A. Portfolio grooming — keep / cut / consolidate / extract existing plugins.
- B. Capability gaps — new plugins/skills worth building, vs adopting an existing tool (buy-vs-build).
- C. Agent triggering & roster — how subagents are defined, why bespoke ones don't fire, what roster earns its place.
- D. Execution economy — model-tiering + context/cache cost (offload cheap mechanical work; pick the right model/effort per task).
- E. Ecosystem hygiene & meta — drift guards, versioning, README/marketplace sync, journal/maintenance automation, self-knowledge.

## Ranked Survivors

### 1. Cause-classified grooming pass — delete/archive/extract, not a blunt purge

Before cutting, classify each zero-fire plugin by *why* it's silent, because "zero usage" has at least four distinct causes and only one justifies a hard delete.

The four causes: dead service-wrapper (delete — git history is the archive), superseded by the base model (delete; seed 5), available elsewhere / already adopted (delete, adopt the external tool; seed 7), and kept-as-reference or personal (archive or extract, don't delete in place). `python-toolkit`/`test-suite`/`docs-generator` may run via raw `bash` with no attribution, so they get a one-time bash-path measurement before any verdict.

This is the literal ask and is almost entirely direct measured evidence. The downside is that deletions are mildly irreversible socially (someone may re-add a wrapper); survivor #6's retention flag is the guard against that.

Per-plugin verdicts: KEEP — saga, team-execution, mission-control, redis-channel, home-lab-ops, unifi. PROBATION — deploy (new, 0 fires, pre-prod tooling; revisit when a prod path exists). CUT — slack, pagerduty, splunk (thin service wrappers), identity-toolkit + sdk-lifecycle (knowledge-only; LLMs now subsume them). EXTRACT — marketplace-lister + todoist-manager (personal/consumer; verify bash-exec first). MEASURE → DECIDE — python-toolkit, test-suite, docs-generator (0 attributed but may run via bash).

| field | value |
|-------|-------|
| basis | direct: zero-attribution corpus data + US1/US5/US6; external: library MUSTIE / restaurant menu-engineering classification |
| confidence | 86 |
| complexity | Low-Med |
| axis | A |
| status | Unexplored |

### 2. Mechanical-ops offload to a cheap throwaway sub-session

Make it a rule that the high-context main session never runs `git commit`/`push`/`PR-open`/`format`/`lint` itself — those ship to a fresh Haiku-tier sub-session that starts near 0% context and returns only the result.

This is seed 3 (the "commit at 90% context is a waste" case) fused with the batch-bash/git-ops seed, and it was the strongest cross-frame consensus in the run (every frame produced it). The write-combining-buffer framing sharpens it: the cost isn't the git work, it's the per-op context overhead in an expensive window; one batched flush returns the same result without the intermediate bash chatter touching main context. The hard forbidden-in-main rule is what forces the offload to actually happen.

The downside is that a handoff contract is needed (scope in, result out) so it isn't "spawn and hope"; the existing `handoff_envelope.py` is the nearest primitive to extend.

| field | value |
|-------|-------|
| basis | direct: US2 + US3 + /compact ×48 + /context ×17 + agy/codex already offload |
| confidence | 85 |
| complexity | Med |
| axis | D |
| status | Unexplored |

### 3. Collapse the agent roster — delete the `agents/` dirs, ban new ones, justify-tier the exceptions

Delete the 9 bespoke domain agent files (zero fires, contradict a twice-rejected convention), add a CI guard that fails on a new `agents/` dir, and allow an agent file only if it justifies a non-default `model`/`effort`/tool-scope in frontmatter.

This is the honest answer to "my agent setup is lacking": the data says the fix is fewer agents, not more. The synaptic-pruning analogy is exact — silent specialized pathways get eliminated and load consolidates onto the high-traffic generic trunks. The justify-tier rule salvages the one legitimate reason to ship an agent file (it needs a different compute/permission profile than the default), linking directly to #5.

The downside is that a few agent files (`sdlc-operator`, `release-orchestrator`) encode real orchestration prompts worth relocating into their skills rather than deleting outright.

| field | value |
|-------|-------|
| basis | direct: 9 bespoke agents @ 0 ad-hoc fires + "NO agents/ dir" convention rejected twice; external: synaptic pruning |
| confidence | 88 |
| complexity | Low |
| axis | C |
| status | Unexplored |

### 4. Generate `marketplace.json` + README from `plugin.json` (single source of truth)

Stop hand-maintaining derived lists: generate the marketplace array and README plugin table from the per-plugin `plugin.json` files, and let the queued P1 CI guard assert the generated files match.

The drift is real and recurring: the README lists 11 of 17 plugins, the marketplace-drift bug shipped twice, there's a standing memory note about the `marketplace.json` editing footgun, and the metadata version is itself ambiguous. The repo's own docs standard ("single source of truth") applies to its own registry. Generation kills the drift class by construction; the P1 guard becomes a cheap backstop.

The downside is a small generator + template to build and maintain; the `create-plugin.sh` scaffold should emit the compliant bundle too.

| field | value |
|-------|-------|
| basis | direct: README 11/17 stale + drift shipped twice + #marketplace-ci-guard (P1) + memory editing-guard; external: apt autoremove |
| confidence | 84 |
| complexity | Low-Med |
| axis | E |
| status | Unexplored |

### 5. Per-task model/effort tiering as declared saga policy

Annotate each saga command with a recommended tier so dispatch picks the model instead of the operator typing `/model` and `/effort` ~140 times — interrogation/review lean high-effort, mechanical handoffs lean cheap, search fan-outs lean cheap-and-wide.

Greenfield: zero journal coverage, and the Agent tool + Workflow `agent()` already support per-call model/effort. Frame it as least-privilege compute (tier × tool-scope × effort = the minimum the task needs), which makes #3's justify-tier rule concrete. Key counter-insight: the win is sometimes tiering down and wide (many Haiku Explore agents + one expensive synthesis pass), not tiering up — so the policy must express "cheap-and-many," not just "smart-and-one."

The downside is that tier defaults can be wrong for an off-distribution task; needs an easy per-invocation override (which already exists).

| field | value |
|-------|-------|
| basis | direct: US4 + /effort ×113 + /model ×28 + "model tiering: ZERO journal coverage"; external: tiered storage / least-privilege |
| confidence | 78 |
| complexity | Med |
| axis | D |
| status | Unexplored |

### 6. Plugin usage ledger + retention flags — make grooming self-maintaining

Add an apt-style `retention` field to each marketplace entry (`core` / `active` / `reference` / `orphan-candidate`) and a ledger that timestamps each plugin's last fire, emitting a quarterly "sunset candidates" report.

This directly answers "we have not done this sort of grooming for quite some time" — the reason it drifted is that keep is the silent default and nothing surfaces orphans. The retention flag is the `apt-mark manual` bit: it encodes intent as data so an automated orphan-prune is safe (it can only ever touch `orphan-candidate`). The ledger turns this ideation into a recurring 10-minute report instead of a once-a-year archaeology dig.

The downside is another small mechanism to maintain; only worth it if the report is acted on.

| field | value |
|-------|-------|
| basis | direct: 11/17 zero-fire + "grooming hasn't happened in a while"; external: apt autoremove / manual flag |
| confidence | 76 |
| complexity | Low-Med |
| axis | E |
| status | Unexplored |

### 7. Buy-vs-build gate at the marketplace door

Make a one-page "does an already-adopted tool cover this?" checklist a merge-blocking item in the plugin PR template, and treat overlap with an adopted external tool as a cut signal for existing homegrown plugins.

This is seed 7 as a structural rule. The corpus shows the operator already routes real work to `agy` (30), `codex` (22), `compound-engineering` (2,578), and `superpowers` (706) — external tools out-fire most of the local portfolio, and several zero-fire plugins are thin API wrappers an MCP server already covers. The gate stops the portfolio from re-growing dead wrappers.

The downside is that a checklist is only as good as the discipline behind it; pair it with #6 so overlap gets caught retroactively.

| field | value |
|-------|-------|
| basis | direct: US5 + agy/codex/CE/superpowers out-fire local plugins |
| confidence | 74 |
| complexity | Low |
| axis | B |
| status | Unexplored |

### 8. Journal-aware lifecycle substrate — the journal plugin, sharpened

Promote the queued `#engineering-journal-plugin` from "template-copier" to a substrate whose read side is a first-class saga primitive: a helper that `/retro`, `/investigate`, `/optimize`, and `/strategy` call to query prior LEARNINGS/DECISIONS before they re-derive a lesson.

The template-copy is the trivial half. The compounding half is that today the journal only pays back when a human re-reads it — a write-only diary. Direct evidence it leaks value: the same provenance trap (`#campaign-brief-merge-is-a-provenance-hypothesis`) fired three times across builds because nothing forced a pre-build journal read.

The downside is that this is the biggest lift here and the read-API design needs care (tag taxonomy, staleness) — highest ceiling, not cheapest.

| field | value |
|-------|-------|
| basis | direct: #engineering-journal-plugin (P2) + provenance trap fired 3× + 2 manual adopters |
| confidence | 72 |
| complexity | Med-High |
| axis | B |
| status | Unexplored |

### 9. Prune LLM-obsolete guards/scaffolding — the seed-5 sweep

Run a deliberate pass over saga's skills asking of each guard "does a current frontier model still misbehave without this, or is it cargo-cult from a weaker-model era?" — and delete what no longer changes behavior.

This is seed 5, and it's greenfield (zero journal coverage of "no longer needed with current LLMs"). Because saga fires 16,502 times, every obsolete guard is a context tax paid on the dominant workflow. Candidates: heavy read-don't-skim rules, elaborate re-grounding ceremonies, defensive deterministic classifiers (the queued `#doc-review-classifier` is exactly an "is this still worth it vs. the model doing it for free?" case).

The downside — flagged by the journal itself — is that removing a guard that is still load-bearing is a silent regression; each removal needs an end-to-end behavior check before it ships. A careful sweep, not a bulk delete.

| field | value |
|-------|-------|
| basis | direct: US6 + "no longer needed with current LLMs: ZERO coverage" + saga 16,502 fires; external: compiler dead-code elimination |
| confidence | 70 |
| complexity | Med |
| axis | A |
| status | Unexplored |

### 10. Saga trajectory telemetry mining — the tick-chain is untapped process data

Build a read-only analytics pass over the saga tick-chains already written (16,502 fires' worth) to find where loops stall, which commands re-run, and where reviews gate — without waiting on a live product.

The queued `#pulse-live-telemetry` is gated on "a live product with telemetry," but the lifecycle already generates dense process-telemetry on every run and throws it away after each `/resume`. The all-ticks reader already exists (shipped with `/resume`), so the marginal cost is just the analytics pass. This also feeds #9 and the per-command fire audit (does every one of saga's 18 commands earn its place?).

The downside is that it's introspective tooling — valuable but not user-facing and easy to over-build; scope it to one concrete question first.

| field | value |
|-------|-------|
| basis | direct: saga 16,502 fires + all-ticks reader exists + #pulse blocked on product |
| confidence | 66 |
| complexity | Med |
| axis | E |
| status | Unexplored |

### 11. Codex/Antigravity as first-class saga execution backends

Fold the delegation already done by hand (`agy` ×30, `codex` ×22) into saga's operator-choice as a 4th/5th backend, so `/work` or `/investigate` can route a task to Gemini or GPT-5 the same governed way it routes to team-execution.

This builds on measured cross-model delegation that currently runs off the lifecycle rails and closes the queued `#delegate-agents-plugin` spike. Lowest confidence of the survivors because the prior 2026-05-30 delegate-agent ideation largely shipped (the `agy`/`codex` plugins exist and work standalone), so the genuinely new value is narrow: the saga-backend framing and a governed handoff contract, not the delegation capability itself.

The downside is real overlap with what already works; revisit prior art before committing.

| field | value |
|-------|-------|
| basis | direct: agy 30 + codex 22 + saga operator-choice = 3 backends only + #delegate-agents-plugin (P2) |
| confidence | 60 |
| complexity | Med-High |
| axis | B |
| status | Unexplored |

## Did not survive (revivable)

Explicit rejection is the quality mechanism. Cut ideas keep stable ids so they can be revived (which re-enters the Phase 3 filter with new evidence).

| id | title | summary | reason | status |
|----|-------|---------|--------|--------|
| R1 | Split saga into spine + phase packs | Break saga into a thin router + on-demand phase packs | Premise that all 18 commands load per-turn is unverified (skills load on invocation; only descriptions are always-present), so the claimed context saving likely doesn't exist — and it contradicts the deliberate engine-merge unify decision | rejected |
| R2 | Saga as 100 micro-plugins | Explode saga into single-command plugins | Subject-distorting (versioning hell, reverses the unify campaign); only real kernel — a per-command fire audit — is folded into #10 | rejected |
| R3 | Context-watchdog / auto-compact hook | A hook that watches context fill and auto-offloads or compacts | Too speculative; the harness already auto-compacts and the journal warns to verify coaching reaches the model; the frugal-defaults kernel is folded into #2/#5 | rejected |
| R4 | Wide-cheap-swarm vs one expensive agent | Many Haiku agents + one synthesis pass | Real insight but a tactic, not a standalone deliverable — folded into #5 as the "tier down and wide" rule | rejected |
| R5 | Bundle dead plugins into one dormant `ops-integrations` | Keep slack/pagerduty/splunk folded into one idle plugin instead of deleting | Dormant code still carries maintenance/sync cost; git history is the archive. Revive if a real on-call/incident-ops need emerges | rejected |

No axis ended with zero survivors. Axis C is intentionally served by a single comprehensive idea (#3) because the data says the agent roster should collapse, not multiply — the honest finding, not a coverage gap.

## Co-ideation log

| source | entered | idea / seed | outcome |
|--------|---------|-------------|---------|
| user-seed | Phase 0 | US1: remove slack, identity-toolkit, pagerduty, splunk, sdk-lifecycle (never used) | survived, refined into #1 (classify-by-cause → delete/archive/extract; the 5 named confirmed CUT) |
| user-seed | Phase 0 | US2: "commit at 90% context" is waste — offload cheap mechanical ops to a sub-session | survived as #2 (strongest cross-frame consensus) |
| user-seed | Phase 0 | US3: an agent that batches bash/git-ops | survived, fused into #2 (write-combining batch sub-agent) |
| user-seed | Phase 0 | US4: agents that pick a different model than the default | survived as #5; the wide-cheap counterpoint (R4) folded in |
| user-seed | Phase 0 | US5: don't build our own for what existing tools cover | survived as #7 (buy-vs-build gate) |
| user-seed | Phase 0 | US6: prune capabilities/guards no longer necessary with current LLMs | survived as #9; the model-obsolescence half also informs #1 |
| user-seed | Phase 0 | Seed 1: scan all repos' transcripts for patterns | executed as grounding method (the measured-usage section), not a pool candidate |
| frame-agent | Phase 2 | Collapse the bespoke agent roster + CI ban + justify-tier | survived as #3 |
| frame-agent | Phase 2 | Generate marketplace.json + README from plugin.json | survived as #4 (sharpens P1 #marketplace-ci-guard from detect to prevent) |
| frame-agent | Phase 2 | Usage ledger + apt-style retention flags | survived as #6 |
| frame-agent | Phase 2 | Journal-aware lifecycle substrate | survived as #8 (sharpens P2 #engineering-journal-plugin) |
| frame-agent | Phase 2 | Saga trajectory telemetry mining | survived as #10 |
| frame-agent | Phase 2 | Codex/Antigravity as saga backends | survived as #11 (lowest conf — prior art largely shipped) |
| frame-agent | Phase 2 | Split saga / 100 micro-plugins / auto-compact hook | cut → R1 / R2 / R3 |
