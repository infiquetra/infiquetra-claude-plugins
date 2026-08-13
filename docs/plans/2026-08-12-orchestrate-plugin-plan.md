---
title: Build the orchestrate plugin — multi-vendor session orchestration on herdr events
type: feat
status: active
date: 2026-08-12
origin: docs/brainstorms/2026-08-12-orchestrate-requirements.md
---

# Build the orchestrate plugin — multi-vendor session orchestration on herdr events

## Summary

Build a new `orchestrate` plugin that takes a desired outcome, plans how to split it across real
agent CLI sessions on multiple vendors, launches them through the `agent` wrapper into herdr, stays
awake on herdr's `events.subscribe` socket, verifies each child by a mechanical predicate, and
reaps on verified completion — while remaining continuously answerable to the operator.

Nine units in three phases: a shared `fleet-core` foundation, the Claude implementation, then the
Codex port with a live cross-runtime round-trip as the acceptance gate.

## Problem Frame

An evidence pass over 552 agent transcripts (100% proof-verified read) found 243 distinct
coordination failures across 477 session-occurrences. Ranked by `cost × silence` rather than count,
the top categories are evidence (51 entries), boundary (39), notification (27), and model-routing
(20) — all failures that present as success. `lifecycle` leads on raw count (130 occurrences) and
ranks near the bottom on severity, because the operator objects out loud every time and it
self-corrects within a round.

**The organizing principle: the operator is already an excellent mechanism for loud failures.
Build for the quiet ones.**

The requirements also established that this is the unbuilt half of `/outcome`'s own R15 — *"one
durable persistent session + worktree per sub-outcome"* — of which only the worktree half shipped
(`outcome_worktrees.py`; `outcome_spec.py:678` states the outcome layer has no session concept).

## Requirements

Plan-level requirements. Each traces to the merged brainstorm (PR #710, squash `d8a9e6aa`);
brainstorm IDs are given in parentheses.

- **R1.** `/orchestrate <outcome>` accepts an issue number, parent issue, requirements doc, or
  prose prompt, with no decomposition required before invocation. (brainstorm R1)
- **R2.** The orchestrator stays awake via herdr `events.subscribe`, not polling, and never
  requires an operator turn to make progress. (R21a, R8)
- **R3.** Completion, readiness, and blocked-state detection subscribe to **content**
  (`pane.output_matched`), never to inferred `agent_status`. (R21b)
- **R4.** State is a single flat register — one row per child plus one for the mirror — persisted
  as a plain JSON file in the repository, written atomically. No graph, no leases, no fencing.
  (§5, C1, C5)
- **R5.** "Done" means a bounded mechanical predicate passes, bound to *this* dispatch by a run id,
  evaluated outside the child's write scope, on a settled artifact, with integration verified
  before reaping. (R10–R13, R14a–d)
- **R6.** The orchestrator performs aggregation and conversation only; its own work goes to a
  persistent mirror that returns distilled conclusions and never evaluates a predicate. (R4–R7,
  R6a–c)
- **R7.** Each child carries its own mutation scope, model, effort, and vendor, chosen by work
  shape from a vendor-neutral tier vocabulary. (R15, R25, R27)
- **R8.** Vendor selection may route for available capacity as well as capability. (R26)
- **R9.** A spend ceiling exists and halts the run when reached. (R28a)
- **R10.** Work in progress is bounded and declared, respecting per-vendor concurrency limits.
  (R31)
- **R11.** `/outcome` is deprecated **mechanically** — by rewriting the `description:` frontmatter
  that drives command selection — in both repositories, and is not deleted. (R2, C12)
- **R12.** Both runtimes read and write the same register with the same meaning, proven by a live
  round-trip in both directions. (C1–C4, C14, C15)

## Key Technical Decisions

**KTD1 — The verb is the surface; the outcome is an argument.** `/outcome` made the noun the
command, forcing work to be shaped as a complete DAG before anything could start. `orchestrate`
discovers the shape during planning. Rejected: extending `/outcome`, which reproduces the up-front
decomposition tax that made it go unused.

**KTD2 — Behaviour lives in skills; Claude adds a thin command loader.** Codex invokes skills
directly (`$saga:work` and similar appear in that repo) and has no `commands/` directory. Claude
needs a `commands/*.md` entry to expose `/orchestrate`, and that file is a ~10-line loader — the
established pattern (`plugins/saga/commands/plan.md` is frontmatter plus *"Load … and run its
phases"*). Both runtimes therefore get a real invocable surface with zero behavioural divergence.
Rejected: skills-only on Claude, which leaves the operator without the slash command he actually
uses.

**KTD3 — The wake mechanism is herdr's socket, not a daemon and not a host-harness feature.**
`events.subscribe` over `~/.config/herdr/herdr.sock` (protocol 19) pushes 26 event kinds; verified
live returning `subscription_started`, real `tab_created`/`tab_closed`, and a `pane.output_matched`
carrying `matched_line` plus a full pane `read`. Any process that can open a unix socket can
subscribe, so autonomy is runtime-portable by construction. Rejected: a separate controller
daemon, and rejected: reducing the tool to operator-triggered verbs — both were proposed by
adversarial review on the false premise that no wake mechanism existed.

**KTD4 — Subscribe to what a child emits, not to what a detector says about it.** herdr ships 22
agent-kind detectors and exactly one is locally owned (`muse-herdr`); they are wrong in
vendor-specific, non-agreeing ways (observed in one day: `agy` `idle`-while-working, `claude`
`working`-after-verified-completion, `muse` never transitioning at all —
`state_change_seq` 297 at launch and 297 at completion). `pane.output_matched` is content-based
and immune to all of it. Detector quality becomes a nice-to-have.

**KTD5 — One table, and richer structures are earned by observed pain.** The register cannot
express "child B needs child A's output"; when that pressure arrives the fix is one `blocked_by`
column, at which point it is a minimal DAG. Rejected: building a graph engine up front.

**KTD6 — The mirror does unbounded reading; it never decides.** Routing the validity predicate
through the mirror makes verification a claim again and reintroduces the highest-severity failure
class one layer up with no second reader (found by adversarial review of the first draft).
Predicates are bounded checks the orchestrator runs inline, which R7 of the brainstorm already
permits. The mirror holds a register row so its own silent failure is visible.

**KTD7 — Converge Claude's `models.json` onto the Codex `lineage_models` shape.** The cross-vendor
tier mapping exists only on the Codex side: Claude's `models.json` has `models`/`efforts`; Codex's
has `lineage_models`, `lineage_efforts`, `execution_classes`, and `root_orchestration_profiles`.
The lineage form is the right shape — a tier name is an abstraction each runtime resolves to its
own concrete model — so a new vendor is a mapping entry, never a change to the tier vocabulary.
Rejected: `orchestrate` vendoring a third model table (the dead-wiring pattern the journal warns
about), and rejected: reading the sibling repository's file across a checkout path.

**KTD8 — No leases, no fencing, no cross-runtime schema gate.** `lease_broker`'s expiry is
same-boot monotonic and its lock is per-host, so cross-machine handoff and lease fencing cannot
both hold; a second objection landed independently — the register lock protects the register while
the real shared resource is the external side effects on herdr tabs. Grounding then found the
module is already being **deleted**: `docs/plans/2026-07-30-issue-677-lease-broker-retirement-plan.md`
unwinds 91 call sites and removes 10,203 lines, and it is already absent from Claude's
`fleet-core`. **Revisit when** a second concurrent orchestrator is ever observed in practice.

**KTD9 — Ship Claude to working before porting to Codex.** The design changed materially three
times during requirements. Building both runtimes in parallel against an unproven design doubles
the rework on the next change and makes the Codex side port a moving target. The shared foundation
(U1) lands first because both runtimes need it.

**KTD10 — The register lives at `.orchestrate/register.json`, a new runtime-neutral top-level
directory.** It must be readable and writable by both runtimes with the same meaning, which rules
out `.claude/` and `.codex/` — mirroring it per runtime forks the exact file the handoff
requirement depends on and needs a sync step that can fail. Rejected: `docs/orchestrations/`, which
gives strong provenance but turns a prose directory into machine state and produces churn commits
while a run is live. Whether `.orchestrate/` is committed or ignored is a per-repository choice.

**KTD11 — The build itself is orchestrated across multi-vendor herdr sessions.** This is the
dogfood: friction encountered while driving the build by hand is direct evidence for the tool being
built. Available native CLIs verified on this host: `claude`, `codex`, `grok`, `muse`, `qwen`,
`agy`. Per-unit vendor assignment follows work shape, and the Codex port is built by a `codex`
session in the Codex repository.

## High-Level Technical Design

```
   operator
      |  (never blocks)
      v
  ORCHESTRATOR ---- events.subscribe ----> herdr socket
      |  aggregation + conversation only        ^
      |                                         | observes
      +--> MIRROR   (unbounded reading)         |
      |                                         |
      +--> register (plain JSON, in repo) <-----+
      |
      +--> agent wrapper --> children: claude codex grok muse qwen agy
```

Layering is fixed: **`orchestrate` decides what/when/how; `agent` + `herdr` do
create/communicate/destroy.** No unit reimplements session creation, prompting, reading, or
closing.

## Implementation Units

Dependency order. Phase boundaries are hard: Phase 1 does not start until U1 lands; Phase 2 does
not start until Phase 1 is dogfooded on real work.

### U1. Port the lineage tier vocabulary into Claude's fleet-core

**Phase 0 — shared foundation. Both runtimes depend on this; nothing else can start.**

**What.** Extend `plugins/fleet-core/scripts/fleet_commons/models.json` with `lineage_models`,
`lineage_efforts`, `execution_classes`, and `root_orchestration_profiles`, matching the Codex
schema. Add resolution in `tier_resolver.py` mapping a tier name plus runtime to a concrete
`{model, effort}`. Existing `models` / `efforts` keys and their readers keep working.

**Why.** Tier routing is the reason the plugin exists (operator's position, recorded), and the
mapping form exists only on the Codex side today.

**Files.** `plugins/fleet-core/scripts/fleet_commons/models.json`,
`plugins/fleet-core/scripts/fleet_commons/tier_resolver.py`,
`plugins/fleet-core/references/tier-palette.md`, plugin release surfaces per repo CLAUDE.md.

**Watch for.** The Codex file's own `lineage_models` maps to `gpt-5.5`/`gpt-5.4` while its
`root_orchestration_profiles` names `gpt-5.6-sol`/`gpt-5.6-terra` — one is stale. Resolve before
porting; do not port the inconsistency.

**Test scenarios** — `tests/test_fleet_core_lineage_models.py`:
existing `models`/`efforts` readers are unaffected by the added keys; a tier name resolves to
different concrete models for the `claude` and `codex` runtimes; an unknown tier raises rather than
defaulting; an unknown runtime raises; the schema round-trips byte-identically for an unchanged
file.

**Suggested vendor/tier.** `claude` opus/high — schema judgment with cross-repo consequences.

### U2. Plugin scaffold and the register

**What.** Scaffold `plugins/orchestrate/` via `tools/create-plugin.sh`. Define the register: a
flat JSON document, one row per child plus one for the mirror, with columns for id, agent, vendor,
model/effort, task, scope, artifact path, predicate, run id, expected state, observed state.
Implement atomic read/write (temp file plus rename) at **`.orchestrate/register.json`**, with
per-run material under `.orchestrate/runs/<run-id>/`.

**Why.** The register is the whole state model (KTD5) and the Claude↔Codex handoff seam (R12).

**Files.** `plugins/orchestrate/.claude-plugin/plugin.json`,
`plugins/orchestrate/skills/orchestrate/SKILL.md`,
`plugins/orchestrate/skills/orchestrate/scripts/register.py`, `.claude-plugin/marketplace.json`.

**Test scenarios** — `tests/test_orchestrate_register.py`:
a fresh register initialises with a schema version; a row round-trips every column; an atomic write
leaves no partial file when interrupted; an unknown top-level key is preserved on write (C4); a
schema version the code does not support halts with a receipt and mutates nothing (C3); two
sequential writers do not lose the first writer's row.

**Suggested vendor/tier.** `claude` sonnet/medium — bounded, well-specified, testable.

### U3. herdr event client

**What.** A client that opens `~/.config/herdr/herdr.sock`, sends
`{"id", "method": "events.subscribe", "params": {"subscriptions": [...]}}`, and dispatches decoded
events. Support global subscriptions (`tab_closed`, `pane_exited` — `type` only) and per-pane ones
(`pane.output_matched`, `pane.agent_status_changed` — require `pane_id`). Handle reconnection.

**Why.** This is the wake mechanism (KTD3) and the thing that makes autonomy possible without a
daemon.

**Verified contract details** — these cost a round each during discovery, so they are recorded:
the API spells the read source `recent_unwrapped` (underscore) where the CLI uses
`recent-unwrapped` (hyphen); `match` is a tagged enum `{"type": "substring"|"regex", "value": ...}`,
not a bare string; a successful subscribe replies `{"result": {"type": "subscription_started"}}`.

**Files.** `plugins/orchestrate/skills/orchestrate/scripts/herdr_events.py`,
`plugins/orchestrate/references/herdr-event-api.md`.

**Test scenarios** — `tests/test_orchestrate_herdr_events.py`:
a subscribe request serialises with the exact verified shape; a malformed subscription is reported
rather than silently dropped; `pane.output_matched` with a regex decodes `matched_line`; a socket
close mid-stream triggers reconnect without losing the subscription set; an unknown event kind is
ignored rather than raising; a socket that does not exist fails with an actionable message.

**Suggested vendor/tier.** `codex` gpt-5.6-sol/high — protocol work with a precise written contract.

### U4. Session lifecycle — launch, readiness, reap

**What.** Launch children through the `agent` wrapper (dry-run preview, confirm `cwd` and
workspace, `--no-focus`, explicit model and effort). Confirm readiness **by interaction**: dispatch,
then require an observed change within a bounded window. Reap on verified completion, recording the
transition in the register so a subsequent absence is legible.

**Why.** Launch success is not readiness (a child can sit on a trust prompt), and a reap the
watcher has no record of raises a false alarm asserting the opposite of the truth.

**Files.** `plugins/orchestrate/skills/orchestrate/scripts/session_lifecycle.py`,
`plugins/orchestrate/references/substrate-contract.md`.

**Test scenarios** — `tests/test_orchestrate_session_lifecycle.py`:
a launch that reports success but never becomes interactive is classified not-ready, not running; a
child blocked on a trust prompt is detected via content and surfaced, never dispatched into; a reap
writes the transition before closing the tab; a child that vanishes without a recorded reap raises,
while one that vanishes after a recorded reap does not; readiness never consults `agent_status`
alone.

**Suggested vendor/tier.** `claude` opus/high — this is where the substrate lies, and judgment about
wrong signals is the unit's substance.

### U5. Completion — predicate, run identity, integration

**What.** Evaluate a child's validity predicate: a bounded mechanical check (file test, required
section, schema parse, test exit code) run **inline by the orchestrator**. Bind the artifact to
this dispatch by run id. Require the artifact to be settled before reading. Require integration to
the destination to be verified before the child is reaped.

**Why.** Evidence is the highest-severity failure category, and each sub-requirement closes a
concrete defect found by adversarial review: a stale artifact satisfying the predicate; a child
weakening the test that certifies it; a predicate passing on a half-written file; verified work
discarded when a worktree is reaped before the change lands.

**Files.** `plugins/orchestrate/skills/orchestrate/scripts/completion.py`,
`plugins/orchestrate/references/predicates.md`.

**Test scenarios** — `tests/test_orchestrate_completion.py`:
an artifact from a previous run with a different run id does not satisfy the predicate; a predicate
whose script lives inside the child's write scope is rejected before evaluation; a truncated
artifact fails rather than passing; reaping is refused while the destination branch is unchanged; a
predicate that errors or hangs is a failure, never a pass; a passing predicate on a settled,
correctly-bound artifact reaps cleanly.

**Suggested vendor/tier.** `claude` opus/high — the highest-severity requirement in the plan.

### U6. Planning and vendor/tier routing

**What.** The judgment step: given an outcome, decide the split into children, and for each one its
agent, vendor, model, effort, scope, artifact, and predicate. Resolve tier from work shape via
`tier_policy.json` and U1's lineage mapping. Allow capacity-based vendor selection. Enforce the WIP
bound via `concurrency_policy.py` (already shared by both `fleet-core`s) and the spend ceiling via
the envelope's `cost_ceiling_tokens`. Show the plan to the operator before any child launches.

**Why.** Routing across models and vendors is the reason the plugin exists.

**Files.** `plugins/orchestrate/skills/orchestrate/scripts/planning.py`,
`plugins/orchestrate/references/routing.md`.

**Test scenarios** — `tests/test_orchestrate_planning.py`:
a judgment-shaped unit resolves to a high tier and a mechanical one to a low tier; the same work
shape resolves to different concrete models for different runtimes; an operator-declared vendor
preference overrides the work-shape default and is recorded as explicit; exceeding the WIP bound
queues rather than launching; reaching the spend ceiling halts and reports; planning never launches
a child.

**Suggested vendor/tier.** `grok` or `codex` high — routing logic with clear inputs and outputs;
good candidate for a non-Claude vendor, which also exercises the multi-vendor path.

### U7. The mirror and the operator channel

**What.** A persistent paired session for the orchestrator's own unbounded work — synthesis,
comparison, bulk reading. Returns distilled conclusions only. Holds a register row. Never
evaluates a predicate and never addresses the operator. Context is managed deliberately (compact or
clear on the orchestrator's instruction).

**Why.** The top failure across the corpus is the operator channel dying under supervision load.

**Files.** `plugins/orchestrate/skills/orchestrate/scripts/mirror.py`,
`plugins/orchestrate/references/operator-channel.md`.

**Test scenarios** — `tests/test_orchestrate_mirror.py`:
a predicate evaluation request routed to the mirror is refused (KTD6); a mirror return exceeding
the distillation bound is rejected rather than absorbed; the mirror has a register row from
creation; a hung mirror raises divergence like any other child; an operator message is answerable
while the mirror is busy.

**Suggested vendor/tier.** `claude` opus/high — the channel-protection invariant is subtle.

### U8. Claude surface and `/outcome` deprecation

**What.** Add `plugins/orchestrate/commands/orchestrate.md` as a thin loader (KTD2). Rewrite
`plugins/saga/commands/outcome.md`'s `description:` frontmatter so it no longer matches
orchestration intent and names `/orchestrate` as the replacement. `/outcome` keeps working when
invoked explicitly; nothing is deleted.

**Why.** Deprecation that does not change the selection field does not stop unintentional
invocation.

**Files.** `plugins/orchestrate/commands/orchestrate.md`, `plugins/saga/commands/outcome.md`,
plugin release surfaces per repo CLAUDE.md.

**Test scenarios** — `tests/test_orchestrate_surface.py`:
the loader's frontmatter carries name, description, and argument-hint; `/outcome`'s description no
longer contains orchestration-intent vocabulary and does name `/orchestrate`; `/outcome`'s skill
and scripts are untouched; the marketplace entry validates.

**Suggested vendor/tier.** `claude` sonnet/medium — mechanical, well-specified.

### U9. Codex port and cross-runtime round-trip

**Phase 2 — does not start until Phase 1 is dogfooded on real work.**

**What.** Port the plugin to `infiquetra-codex-plugins` as a skills-only plugin with a
`.codex-plugin/plugin.json`. Converge that repo's `models.json` with U1's. Apply the same
`/outcome` deprecation there (17 outcome scripts live on that side). Prove interop with a live
round-trip in **both** directions.

**Why.** Starting an orchestration under one runtime and resuming under the other is the stated
requirement, and the lossy-write failure is directional so a one-way test would miss it.

**Files.** In `infiquetra-codex-plugins`: `plugins/orchestrate/**`,
`plugins/fleet-core/scripts/fleet_commons/models.json`, `plugins/saga/skills/outcome/**`
description surface, `.agents/plugins/marketplace.json`.

**Operating constraint.** When Claude Code works in that repository, its `plugins/` directory is
the artifact under repair, never session tooling. Its `saga.py`, validators, and renderers must not
be invoked to drive the session.

**Test scenarios** — `tests/test_orchestrate_cross_runtime.py` (both repos):
a register written by Claude is read by Codex with every field intact; the reverse holds; a field
written by one runtime and unknown to the other survives a write by the other (C4); a
`schema_version` neither supports halts with a receipt; the live round-trip launches a child under
one runtime, hands off, and reaps it under the other.

**Suggested vendor/tier.** `codex` gpt-5.6-sol/high, working in the Codex repository — the port
is built by the runtime it targets.

## Scope Boundaries

**Out of scope — not built, so that adding them later is a decision rather than drift.**

- A DAG or graph engine. The register plus a future `blocked_by` column covers it; `/outcome`
  exists if a real DAG appears.
- A reconcile loop. `/outcome` already implements level-triggered reconciliation.
- A background daemon or controller process. `events.subscribe` supplies the wake (KTD3).
- Leases, fencing, and expiry (KTD8).
- A cockpit or dashboard. Aggregation into the conversation replaces it; a surface to go *look at*
  reintroduces the failure this design targets.
- A notification protocol of our own. herdr already provides one; we consume it.
- Automated per-vendor quota discovery. The operator supplies quota state for now.

**Deferred to follow-up work.**

- **The Headroom proxy guard.** `headroom/proxy/handlers/anthropic.py:2150` tests
  `provider_name == "anthropic"`, which labels the *protocol spoken* rather than the *upstream
  answering*, so Anthropic-protocol local models (Muse, Ollama, DeepSeek via Claude Code as
  harness) receive a Claude-only capability and fail with HTTP 400. Third-party package; fixing it
  would unlock those routes but is not a dependency — native CLIs work today.
- **herdr detector coverage.** `herdr integration install` lists neither `muse` nor `agy`. Closing
  those gaps improves the operator's sidebar, which has no predicate to fall back on.
- **`fleet-core` convergence beyond `models.json`.** Nine Claude-only and four Codex-only modules
  remain; only the tier mapping is required here.
- **Codex skill bodies referencing Claude syntax.** That repo's `SKILL.md` files say `/plan` where
  a Codex operator would type `$saga:plan`.
- **`/outcome` cull.** Deprecated here, deleted later, on a condition the operator sets after real
  use.

## Risk Analysis & Mitigation

**The substrate changes under us.** herdr detection behaviour has shifted on past upgrades, and
21 of 22 detectors are upstream. *Mitigation:* KTD4 — content subscriptions rather than detector
state, so an upgrade that changes detection semantics does not change our correctness.

**The dogfood biases the design.** This session drives the build and is also the thing being
replaced. *Mitigation:* friction is recorded as evidence rather than resolved silently, and Phase 1
must be dogfooded on unrelated real work before Phase 2 begins.

**`models.json` convergence breaks existing readers.** U1 touches a file other components read.
*Mitigation:* additive keys only, existing readers covered by test, and the round-trip test proves
byte-identity for unchanged content.

**Scope re-expansion.** Two adversarial reviewers pushed to cut roughly a third of this, including
the tier routing that motivates the work. The operator rejected those cuts with reasons recorded in
the brainstorm. *Mitigation:* the Scope Boundaries section above is the guard; adding anything from
the not-built list requires an explicit decision.
