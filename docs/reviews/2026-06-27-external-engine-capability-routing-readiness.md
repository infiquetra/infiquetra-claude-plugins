---
date: 2026-06-27
target: docs/brainstorms/2026-06-27-external-engine-capability-routing-requirements.md
reviewed_revision: working tree
review_type: requirements readiness (saga /doc-review)
verdict: READY
blocked: false
---

# Readiness Review — External-Engine Capability Routing

## Verdict

**READY for `/plan`.** No `P0` or `P1` findings remain after fixes. The requirements doc safely binds
implementation: roles, trust boundaries, fallback behavior, and safety defaults are now explicit, and
the binding-decision claims it rests on are verified against the repo. Remaining open items are
genuine `/plan`-level design choices (registry packaging, capability taxonomy, the team-execution
wrapper contract), recorded as Outstanding Questions — not readiness gaps.

## Method

Reviewed as a requirements artifact (readiness-skeptic pass; no formal SDLC rubric applies to a
brainstorm doc). Adversarial depth came from a **three-engine panel as gated generators under
Claude-side verification** — every finding was verified against the doc or repo source before
adoption; nothing was adopted on an engine's say-so:

- **Codex / gpt-5.5** at `xhigh`, read-only, with repo access (verified the file:line claims directly).
- **agy Gemini 3.1 Pro (High)**, hermetic (doc inlined).
- **agy Gemini 3.5 Flash (High)**, hermetic (doc inlined).

The cross-family panel earned its keep twice: the two Gemini engines **converged** on the two
highest-value design findings (independent corroboration), and Codex's repo access caught a
citation error the hermetic engines could not see. One Gemini finding was **refuted** by repo
evidence — the reason Claude-side verification is mandatory.

## Applied fixes

All evidence-backed; the doc was edited in place.

| # | Fix | Source | Evidence |
|---|---|---|---|
| 1 | Protocol is assembled into the engine's own payload and forwarded **verbatim**; wrapper never paraphrases or shell-interpolates it (R9, R11, AE5) | Gemini Pro P0 + Flash P2 (converged) | doc R9/R11 self-consistency; the "executable protocol" intent in Key Decisions |
| 2 | Override is pre-dispatch/advisory; autonomous backends act on standing config + surface post-hoc, never block (R20) | Gemini Pro P1 + Flash P1 (converged) | contradiction between R7 dispatch mode and R20 as written |
| 3 | Reframed "never gatekeepers" as a decision **this capability establishes** (parroting = evidence, not the decision); `/plan` writes the real `DECISIONS.md` entry (Key Decisions, Dependencies) | Codex P1 | `DECISIONS.md:276-290` is rationale for the outcome-orchestration plan, not a standing governance decision (verified) |
| 4 | codex/agy reframed as **external** substrate (system CLIs + plugins from another marketplace); added preflight-availability requirement (Dependencies, R24/R26) | Codex P1 | `.claude-plugin/marketplace.json` registers only the 7 infiquetra plugins (verified); `which codex/agy` → external paths |
| 5 | Added R23 — external workers are **evidence-only / non-mutating by default**; mutation requires the ideation-R14 sandbox | Codex P2 (safety) | doc deferred sandbox to ideation R14 while shipping external-as-worker; clobber-risk precedent |
| 6 | Added R24 — fallback/substitution emits a **visible provenance note** (mirrors `orchestration_downgrade`); degradation never silent (R8, R17, AE2 updated) | Codex P2 | `execution-spec.md:136-138` durable-downgrade pattern (verified) |
| 7 | Added R25 — resolver respects the variant **context-window limit** (Codex-CLI 400K); no silent truncation | Gemini Pro P1 | doc's own Seed Data 400K note vs R12 context package |
| 8 | Added R26 — an **explicitly-named** unavailable engine **halts**, no silent substitution (AE6) | Gemini Pro P1 | gap between R8 (no-fit fallback) and R19 (explicit request) |
| 9 | R1/R6 — registry defines a **default variant per engine** for engine-only requests | Gemini Pro P2 | R1 keyed by variant vs R6 naming an engine |
| 10 | R1/R16 — registry models **composing roles/panels** (reviewer panel ≠ single entry) | Gemini Flash P2 | R16 multi-reviewer role vs R1 single-variant entries |
| 11 | R12 + Dependencies — team-execution external-wrapper **context-package contract is a prerequisite to define**, not an existing affordance | Codex P1 + Flash (refuted P0 kernel) | `team-execution SKILL.md` worker contract is plan/reference rows; no wrapper slot (Codex, verified) |
| 12 | Seed Data — per-row **source attribution required at seed time**; full source lists recorded in this artifact | Codex P2 | doc named only broad source categories |
| 13 | Upgraded four "agent-reported / re-confirm at /plan" hedges to **verified** with line numbers | Claude-side verification | `execution-spec.md`, `lifecycle_state.py`, `DECISIONS.md`, `operator-choice.md` read directly |

## Findings by priority (post-fix status)

| Priority | Finding | Engine(s) | Status |
|---|---|---|---|
| P1 | Protocol re-authored by wrapper → non-deterministic drift | Pro + Flash | Fixed (R9/R11/AE5) |
| P1 | Parroting decision mis-cited as binding rule | Codex | Fixed (Key Decisions/Dependencies) |
| P1 | codex/agy substrate assumed present, not preflight-checked | Codex | Fixed (Dependencies, R24/R26) |
| P1 | External-worker mutation outruns deferred sandbox safety | Codex | Fixed (R23) |
| P1 | Override contradicts autonomous dispatch | Pro + Flash | Fixed (R20) |
| P1 | Context-window overflow (Codex 400K) unhandled | Pro | Fixed (R25) |
| P1 | Explicit-engine unavailability undefined | Pro | Fixed (R26) |
| P2 | Silent Claude fallback breaks durable-downgrade pattern | Codex | Fixed (R24/AE2) |
| P2 | Seed data not per-row auditable | Codex | Fixed (Seed Data note) |
| P2 | Default-variant-per-engine missing | Pro | Fixed (R1/R6) |
| P2 | Panel modeled as single entry | Flash | Fixed (R1/R16) |
| P2 | team-execution wrapper contract undefined | Codex + Flash | Fixed as explicit prerequisite (R12/Deps) |
| P0 | "team-execution has no tool-execution privileges" | Flash | **Refuted** — validators run scanners (Semgrep/Bandit); real kernel folded into #11 |
| — | Capability taxonomy (fixed vs free-form) | Flash | Deferred to `/plan` (Outstanding Questions) |

## Residual risk

- **GPT-5.5 second-opinion/refuter behavior is unmapped** — no data on whether it genuinely disagrees
  or parrots under pressure. The doc records this as an assumption; the registry seed flags it. Only
  operator use will resolve it.
- **Seed capability data is 2026-current and from web research** (Sonnet agents, corroboration-tagged).
  It is explicitly seed, not load-bearing — R3/R4/R21 make it editable and dated. Per-row source IDs
  must be attached at seed time (fix #12).
- **The team-execution wrapper contract is unproven** until `/plan` defines the context-package slot;
  inline and cc-workflows dispatch are the lower-risk paths.

## Captured capability-research sources (for registry seeding)

Attach these per-row at seed time, each with OFFICIAL/INDEPENDENT tag + corroboration strength.

Benchmark: OpenAI GPT-5.5 model card (OFFICIAL); Google DeepMind Gemini 3.1 Pro + 3.5 Flash model cards
(OFFICIAL); Artificial Analysis (Gemini 3.1 Pro, 3.5 Flash) (INDEPENDENT); LM Council cross-model table
(INDEPENDENT); LLM-Stats GPT-5.5 (INDEPENDENT); PromptLayer Gemini latency/cost (INDEPENDENT).
Practitioner: MindStudio GPT-5.5 + Flash-vs-Pro reviews; Git AutoReview "best AI for code review";
Phil Schmid "Gemini 3 prompting best practices"; HN Gemini 3.5 Flash thread; SycEval (LLM sycophancy);
practitioner comparison write-ups (contracollective, gitautoreview). Key corroborated [STRONG] findings:
different model family is the best sycophancy mitigation; no model meaningfully less sycophantic;
benchmark deltas <2% are noise; Gemini over-eagerness is a recurring family failure mode; Gemini Pro is
**not** the expert-writing engine (route long-form writing to Claude).

## Next step

Hand off to `mission-control` as a `capability` issue on the operations board (objective
`improve-claude-plugins`), same pipeline as S-1 (#275), S-7 (#277), S-5 (#278), S-2 (#279), S-3 (#281).
Recipient action: `/plan` (requirements-ready; the Outstanding Questions are the planning agenda).
