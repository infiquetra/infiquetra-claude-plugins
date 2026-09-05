---
date: 2026-06-19
topic: plugin-grooming-next-steps
companion-to: 2026-06-19-plugin-ecosystem-grooming-ideation.md
repo: infiquetra-claude-plugins
maturity: idea-ready
---

# Plugin Grooming — Next-Step Seeds

Companion to [`2026-06-19-plugin-ecosystem-grooming-ideation.md`](2026-06-19-plugin-ecosystem-grooming-ideation.md). Three self-contained, ready-to-use artifacts derived from the operator dispositions (Phase 6): an **execution checklist** for the cut, a **`/brainstorm` seed** for Track 2, and a **`/ideate` seed** for Track 1.

---

## 1. The cut — execution-ready (→ `/plan` or direct; NOT a brainstorm)

Nothing fuzzy remains, so this is mechanical, not a brainstorm. The marketplace goes from **17 → 7 keep, 9 cut, 1 relocate**.

| plugin | action | note |
|---|---|---|
| saga, team-execution, mission-control, redis-channel, home-lab-ops, unifi, **deploy** | **KEEP** | all fire (deploy works with saga) |
| slack, pagerduty, splunk | **CUT** | 0 fires; thin service wrappers |
| identity-toolkit, sdk-lifecycle | **CUT** | 0 fires; knowledge-only; current LLMs subsume them |
| python-toolkit, test-suite, docs-generator | **CUT** | 0 fires; rebuild later if a real need appears |
| todoist-manager | **CUT** | move to the Todoist MCP |
| marketplace-lister | **RELOCATE** | move to `infiquetra-hermes-plugins` (built for a hermes agent) |

**Execution notes:**

- Do it as one PR that honors the release contract: each removal drops the plugin dir + its `marketplace.json` entry + its README row + bumps the marketplace metadata version + updates the version/metadata drift tests. Pair this with survivor #4 (generate `marketplace.json` + README from `plugin.json`) so the registry is regenerated from the groomed set instead of hand-edited — that sidesteps the marketplace-drift footgun that has shipped twice.
- Pre-cut safety checks: (a) grep that no KEPT plugin imports/references a cut one; (b) confirm the Todoist MCP is configured before removing `todoist-manager` so the capability isn't lost; (c) no archive branch needed — git history is the archive.
- Relocate: move `plugins/marketplace-lister/` into `infiquetra-hermes-plugins`, register it in that marketplace, and remove it from this one.
- Optional tracking: file a mission-control issue "Groom plugin portfolio 17→7" — or just execute. This is `/plan`-or-do work, not a brainstorm.

---

## 2. Track 2 — `/brainstorm` seed: self-grooming improve stage

Ready for `/brainstorm`. Folds survivors #6 + #7 + #10, minus what `/retro` already does.

**Seed (the chosen idea to deep-dive):**

> A repeatable, periodic **plugin-portfolio grooming capability** for the saga lifecycle — essentially *this grooming session, productized*. On demand (and/or scheduled) it: (a) reports plugin/skill usage and token cost by reading **existing telemetry** — the Langfuse traces (tool calls + token usage + `skill:<name>` tags) plus the `~/.claude` transcript back-catalog — rather than a new ledger; (b) **always searches existing marketplaces first** (pre-seeded locations) for prior art before any "build" suggestion; (c) flags dead/orphan plugins against a retention policy; and (d) proposes net-new skills/agents from observed work-patterns. It also defines an **after-action-report (AAR)** format for the "improve" stage.

**What already exists — do NOT rebuild (verified 2026-06-19):**
- `/retro` Phase 5a already does **new-skill / plugin detection** ("repeated friction a new skill/plugin would remove").
- `/retro` Phase 1.5 already **mines session transcripts** (reuses the `/resume` forensic substrate, file-mediated).
- `/retro` Phase 3 already **writes a retro doc** (the AAR is an enhancement of this, not a new thing).
- The **Langfuse plugin** (`langfuse-observability` v1.0.0) already captures tool calls + token usage + per-turn `skill:` tags.
- The saga **all-ticks reader** already exists (shipped with `/resume`) for trajectory mining.

**The central design fork to resolve in the brainstorm:** a NEW `/groom` skill vs. a "portfolio mode" of `/retro`. Recommended lean: a **separate skill** — `/retro` is terminal and per-work-loop; portfolio grooming is periodic and cross-cutting, so bolting a corpus-wide scan onto `/retro` muddies its job. Share the new-skill-detection logic; don't merge the commands.

**Pre-seed the existing-plugin search with:** the official `claude-code-plugins` and `claude-plugins-official` marketplaces, `awesome-claude-code-plugins`, `langfuse-observability`, and infiquetra's own marketplaces (`infiquetra-claude-plugins`, `infiquetra-hermes-plugins`, `infiquetra-codex-plugins`, `infiquetra-antigravity-plugins`).

**Open questions for the brainstorm:** cadence (on-demand vs scheduled cron); does it emit issues or just a report; how it dedupes against `/retro`; the "dead" threshold (zero fires over N days); whether retention flags live in `marketplace.json` (the apt-style `core`/`active`/`reference`/`orphan-candidate` idea from survivor #6).

**Expected output:** a `requirements-ready` brainstorm doc for the grooming capability.

---

## 3. Track 1 — `/ideate` seed: net-new skills & cheap-tier agents from how I actually work

Folds survivors #2 + #3-roster + #5. Paste the block below as the argument to `/saga:ideate` to start Track 1. It deliberately instructs a **heavier grounding than the run that produced this doc**: mine commit history + transcripts for recurring *work-patterns*, not plugin fire-counts.

**Seed prompt (copy-paste into `/saga:ideate`):**

> Generate candidate net-new, well-triggered **skills** and justified cheap-tier **subagents** for `infiquetra-claude-plugins`, grounded in how I actually work — mined from my **commit history and `~/.claude` transcripts**, not just usage counts. I want a LIST of well-defined, reliably-triggered skills/agents that offload recurring or mechanical work off the main (expensive, high-context) session and onto the right model tier.
>
> Ground the run by mining for recurring WORK-PATTERNS, not plugin fire-counts:
> - repeated multi-step git/PR sequences (the "commit at 90% context" case)
> - repeated bash batches (test+lint+typecheck gates, build/deploy sequences)
> - repeated review / debug / research loops that follow a stable shape
> - anything I do by hand repeatedly that has a deterministic trigger
>
> For each candidate decide: is it a SKILL (main-context instructions, reliable trigger) or a cheap-tier AGENT (separate context, pinned model + narrow tools)? Every candidate must declare: its trigger, skill-vs-agent, and — if an agent — its model tier (haiku/sonnet) and tool scope, with the justification (an agent only earns a file if it pins a cheaper tier or narrower tools). The git-ops / commit offloader is the worked example: a haiku, Bash-only agent fed a tight handoff that returns just the SHA.
>
> Honor the binding convention: no bespoke domain agents on the default model (those are being deleted). Skills are preferred for reliable triggering; agents are for cheap isolated execution.
>
> Constraints: don't propose anything that duplicates an already-installed tool (agy, codex, compound-engineering, superpowers, commit-commands, langfuse) — search and note overlaps. Don't re-propose anything already in `/retro` (new-skill detection) or the items parked in `2026-06-19-plugin-ecosystem-grooming-ideation.md`.

**Why ideation, not brainstorm:** the goal is to *generate a list* from patterns (divergent), not to shape one chosen idea into requirements (convergent). Model-tiering (#5) folds in — each candidate declares its tier. The one separable piece left for later: a tier policy for the *existing* saga commands.
