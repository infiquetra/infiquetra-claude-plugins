---
title: Build the orchestrate plugin — multi-vendor session orchestration on herdr events
type: feat
status: active
date: 2026-08-12
revision: 2
origin: docs/brainstorms/2026-08-12-orchestrate-requirements.md
review: docs/reviews/doc-review-orchestrate-plan-2026-08-13.md
---

# Build the orchestrate plugin — multi-vendor session orchestration on herdr events

## Summary

Build a new `orchestrate` plugin that takes a desired outcome, plans how to split it across real
agent CLI sessions on multiple vendors, launches them through the `agent` wrapper into herdr, stays
awake through a subscriber that holds herdr's `events.subscribe` socket across turns, verifies each
child by a mechanical predicate, and reaps on verified completion — while remaining continuously
answerable to the operator.

Ten units in three phases: a shared `fleet-core` foundation, the Claude implementation, then the
Codex port with a live same-host cross-runtime round-trip as the acceptance gate.

**Revision 2** incorporates a three-engine document review (Claude, codex `gpt-5.6-sol` max,
grok-4.6 xhigh) recorded at `docs/reviews/doc-review-orchestrate-plan-2026-08-13.md`. Four P0 and
eleven P1 findings are resolved below; the operator settled the two that were product decisions.

## Problem Frame

An evidence pass over 552 agent transcripts (100% proof-verified read) found 243 distinct
coordination failures across 477 session-occurrences.

> **Where the evidence lives.** The ledger, its 15 per-shard inputs, the mining scripts, the five
> adversarial reviews, and the second-instrument re-mine that recovered 17 findings from 138
> sessions previously reported empty are archived **outside this repository**, at
> `iCloud Drive/Infiquetra-LLC/Engineering/orchestrate-plugin-evidence-2026-08-13/` (35 files,
> ~830 KB, `README.md` orients it). It is operator-local by decision: the material is mined from
> working sessions across every Infiquetra project and this repository is public. An agent executing
> this plan cannot open it and should treat the numbers above as given rather than re-deriving them.

Ranked by `cost × silence` rather than count,
the top categories are evidence (51 entries), boundary (39), notification (27), and model-routing
(20) — all failures that present as success. `lifecycle` leads on raw count (130 occurrences) and
ranks near the bottom on severity, because the operator objects out loud every time and it
self-corrects within a round.

**The organizing principle: the operator is already an excellent mechanism for loud failures.
Build for the quiet ones.**

The requirements also established that this is the unbuilt half of `/outcome`'s own R15 — *"one
durable persistent session + worktree per sub-outcome"* — of which only the worktree half shipped
(`outcome_worktrees.py`). The outcome layer has no terminal-session concept: `outcome_spec.py` and
`references/outcome-spec.md` contain zero references to herdr, panes, or agent CLIs, and
`outcome_spec.py:678` notes in passing that the outcome layer has no notion of even
`execution_spec`'s pilot barrier edge.

## Requirements

Plan-level requirements. Each traces to the merged brainstorm (PR #710, squash `d8a9e6aa`);
brainstorm IDs are given in parentheses.

- **R1.** `/orchestrate <outcome>` accepts an issue number, parent issue, requirements doc, or
  prose prompt, with no decomposition required before invocation. (brainstorm R1)
- **R2.** The orchestrator makes progress without an operator turn. A **subscriber** — a
  single-purpose child process holding herdr's `events.subscribe` socket — persists across turns and
  wakes the orchestrator by injecting into its pane. (R21a, R8)
- **R3.** Completion, readiness, and blocked-state detection subscribe to **content**
  (`pane.output_matched`), never to inferred `agent_status`, and each match is bound to a
  run-specific sentinel emitted after dispatch. (R21b)
- **R4.** State is a single flat register — one row per child, one for the mirror, one for the
  subscriber — persisted as one plain JSON file **per run**, addressed by `run_id` in an
  orchestrator-owned host-local directory (default `~/.orchestrate/registers/<run_id>.json`,
  the same class of location as the run secret). Written atomically. No graph, no leases, no
  fencing. A `run_id` is host-global on this machine. `retire_run` forgets the per-run
  secret first, then archives the document into the repository at
  `.orchestrate/runs/<run_id>/register-final.json` and deletes the live file and the
  recorded-root sidecar. Forgetting the key requires the coordinator-recorded work
  location. A second retire repairs a leftover key only when that record is still there
  to name the generation, so a reused id is a new authentication identity.
  *(Amended 2026-08-14: the live file is no longer repo-local.
  Repo-locality of the live register put orchestrator-private state inside every child's
  landing. Provenance is the retirement archive. Interoperability on one host (R12) is
  unchanged.)* (§5, C1, C5)
- **R5.** "Done" means a bounded mechanical predicate passes, bound to *this* dispatch by a run id,
  evaluated outside the child's write scope, on a settled artifact, with integration verified
  before reaping. **Judgment work additionally requires a depth sample by an independent verifier**
  (brainstorm R14, retained and narrowed). (R10–R14)
- **R6.** The orchestrator performs aggregation and conversation only; its own work goes to a
  persistent mirror that returns distilled conclusions and never evaluates a predicate. (R4–R7,
  R6a–c)
- **R7.** Each child carries its own mutation scope, model, effort, and vendor, chosen by work
  shape from a vendor-neutral tier vocabulary. Scope is **enforced**, not merely recorded. (R15–R18,
  R20, R25, R27)
- **R8.** Vendor selection may route for available capacity as well as capability, using the
  ordered `fallbacks` already carried by the tier policy. (R26)
- **R9.** A spend ceiling exists and halts the run when reached, measured from **observed** per-child
  token actuals recorded in the register. A vendor that exposes no usage signal fails closed against
  a declared worst-case reservation. (R28a)
- **R10.** Work in progress is bounded and declared **per vendor** as well as in aggregate. (R31)
- **R11.** `/outcome` is deprecated **mechanically** — by rewriting the `description:` frontmatter
  that drives command selection — in both repositories, and is not deleted. (R2, C12)
- **R12.** Both runtimes read and write the same register with the same meaning **on one host**,
  proven by a live round-trip in both directions. Cross-machine handoff is deferred. (C1–C4, C14,
  C15)

## Key Technical Decisions

**KTD1 — The verb is the surface; the outcome is an argument.** `/outcome` made the noun the
command, forcing work to be shaped as a complete DAG before anything could start. `orchestrate`
discovers the shape during planning. Rejected: extending `/outcome`, which reproduces the up-front
decomposition tax that made it go unused.

**KTD2 — Behaviour lives in skills; Claude adds a thin command loader.** Codex invokes skills
directly (`$saga:work` and similar appear in that repo) and has no `commands/` directory. Claude
needs a `commands/*.md` entry to expose `/orchestrate`, and that file is a ~20-line loader — the
established pattern (`plugins/saga/commands/plan.md`, 21 lines: frontmatter, *"Load … and run its
phases"*, a short scope paragraph naming what the command does and does not do, and `$ARGUMENTS`).
Both runtimes therefore get a real invocable surface with zero behavioural divergence.
Rejected: skills-only on Claude, which leaves the operator without the slash command he actually
uses.

**KTD3 — The wake is herdr's socket, held by a subscriber that is a tracked child.**
`events.subscribe` over `~/.config/herdr/herdr.sock` (protocol 19) pushes 26 event kinds; verified
live returning `subscription_started`, real `tab.created`/`tab.closed`, and a `pane.output_matched`
carrying `matched_line` plus a full pane `read`.

A socket subscription needs a live process, and an agent session executes only during turns.
**The orchestrator therefore spawns a subscriber:** a small, single-purpose process that holds the
socket across turns and wakes the orchestrator by injecting into its pane via `agent.prompt`.

This is a controller process, deliberately, and revision 1's blanket exclusion of one was wrong —
it made R2 unsatisfiable. The exclusion is narrowed rather than removed: **no general-purpose
daemon with its own state, lifecycle, or product surface.** The subscriber holds a register row like
any other child, so its own death is a visible divergence rather than a silent stall. Rejected: a
blocking `events.wait` inside one long turn, which is honest and needs no new process but makes R2
false the moment a run outlives a turn; and rejected: reducing the tool to operator-triggered verbs.

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

**KTD7 — Adopt Codex's `execution_classes`, not its `lineage_models`.** *(Rewritten in revision 2.)*
The Codex `models.json` `_comment` is explicit: *"lineage_models/lineage_efforts preserve the
pre-cutover Claude-derived vocabulary **for existing consumers only**. scalar_efforts,
execution_classes, and root_orchestration_profiles are the **authoritative Codex policy**."*

Revision 1 proposed porting `lineage_models`, which is wrong three ways: the `gpt-5.5` versus
`gpt-5.6-sol` "drift" it told the implementer to resolve is not drift but a frozen legacy table
beside a live one; `lineage_models` carries only `codex_model`/`codex_effort`, so the table called
the right multi-vendor shape resolves exactly one vendor; and Codex's `tier_palette.py` requires the
complete five-section version-2 shape and rejects unexpected sections, so convergence by adding
Claude's keys would break Codex at import.

`execution_classes` is the right shape and already carries two things the plan otherwise had no
implementation for:

```
execution_classes."review-max" = {
  order: 0,
  workspace_boundary: "read-only",   <- R7's per-child mutation scope
  external_boundary:  "none",
  preferred:  {model: "gpt-5.6-sol", effort: "max"},
  fallbacks: [ {gpt-5.6-terra, max}, {gpt-5.5, "strongest-supported"} ]
}                                     <- R8's capacity routing
```

Rejected: `orchestrate` vendoring a third model table (the dead-wiring pattern the journal warns
about); rejected: reading the sibling repository's file across a checkout path; rejected:
byte-equal `models.json` convergence, replaced by a declared portable subset plus runtime-owned
policy where the repositories intentionally differ.

**KTD8 — No leases, no fencing, no cross-runtime schema gate.** `lease_broker`'s expiry is
same-boot monotonic and its lock is per-host, so cross-machine handoff and lease fencing cannot
both hold; a second objection landed independently — the register lock protects the register while
the real shared resource is the external side effects on herdr tabs. Grounding then found the
module is already being **deleted**: `docs/plans/2026-07-30-issue-677-lease-broker-retirement-plan.md`
unwinds 91 call sites and removes 10,203 lines, and it is already absent from Claude's
`fleet-core`. **Revisit when** a second concurrent orchestrator is ever observed in practice.

**KTD9 — Ship Claude to working before porting to Codex.** The design changed materially three
times during requirements and again at review. Building both runtimes in parallel against an
unproven design doubles the rework on the next change and makes the Codex side port a moving target.
The shared foundation (U1) lands first because both runtimes need it.

**KTD10 — The live register is addressed by `run_id` in an orchestrator-owned host-local
directory.** Default `~/.orchestrate/registers/<run_id>.json`, relocatable by
`ORCHESTRATE_REGISTER_DIR`. It must be readable and writable by both runtimes with the same
meaning **on one host and one checkout** (R12), which still rules out `.claude/` and
`.codex/` — mirroring it per runtime forks the exact file the handoff depends on. Two
checkouts of one `run_id` are a collision. The original wording placed that
file at `.orchestrate/register.json` inside the repository for interoperability and
provenance. Interoperability on one host does not require a repo-local path: two runtimes
already share `~/.orchestrate/run-secrets`. Provenance is the retirement archive at
`.orchestrate/runs/<run_id>/register-final.json`. Repo-locality of the *live* file put
orchestrator-private state inside every child's landing. Rejected: `docs/orchestrations/`,
which gives strong provenance but turns a prose directory into machine state. **In this
repository `.orchestrate/` is gitignored** for the retirement archive and other run
material.

**KTD11 — The build itself is orchestrated across multi-vendor herdr sessions.** This is the
dogfood: friction encountered while driving the build by hand is direct evidence for the tool being
built. Available native CLIs verified on this host: `claude`, `codex`, `grok`, `muse`, `qwen`,
`agy`. Per-unit vendor assignment follows work shape, and the Codex port is built by a `codex`
session in the Codex repository.

**KTD12 — Event delivery is not durable, so every reconnect runs a bounded catch-up.**
*(New in revision 2.)* Protocol 19 has no subscription cursor, no `since` parameter, and no replay:
every `seq` in the schema is a write-side optimistic-concurrency token or `AgentInfo`'s
`state_change_seq`. Re-subscribing restores **future** delivery only, so an orchestrator or
subscriber restart permanently loses every event in the gap — a child finishes, its events reach
nobody, and the register reads `running` forever.

At startup and after every reconnect, the subscriber therefore runs one catch-up pass: read the live
herdr snapshot for each registered handle, compare expected against observed state, and re-evaluate
run-bound artifacts and predicates. This is **edge-triggered boundary recovery, not a reconcile
loop** — it runs once per reconnect, never on a schedule, and the "no reconcile loop" boundary
stands.

**KTD13 — Handoff is same-host for this release.** *(New in revision 2.)* Companion C1 says "a
different runtime or machine." Same-host is what this release promises: pane ids are herdr-session
local, a register file in one checkout does not reach another clone, and a local socket cannot
observe a remote pane. Cross-machine needs host identity in every row, a register transport with a
conflict rule, and remote herdr routing — deferred as a decision rather than dropped.

## High-Level Technical Design

```
   operator
      |  (never blocks)
      v
  ORCHESTRATOR <---- agent.prompt ---- SUBSCRIBER  (register row; holds
      |  aggregation + conversation only    ^        the socket across turns,
      |                                     |        catch-up on every reconnect)
      +--> MIRROR   (unbounded reading)     | events.subscribe
      |                                     v
      +--> register (plain JSON, in repo) <---- herdr socket
      |                                          ^
      +--> agent wrapper --> children: claude codex grok muse qwen agy
                                  |                    |
                                  +-- emit run sentinel +
```

Layering is fixed: **`orchestrate` decides what/when/how; `agent` + `herdr` do
create/communicate/destroy.** No unit reimplements session creation, prompting, reading, or
closing.

## Implementation Units

Dependency order. Phase boundaries are hard: Phase 1 does not start until U1 lands; Phase 2 does
not start until Phase 1 is dogfooded on real work per the gate in U8.

### U1. Port the authoritative tier vocabulary into Claude's fleet-core

**Phase 0 — shared foundation. Both runtimes depend on this; nothing else can start.**

**What.** Settle the routing contract, then implement it. Extend
`plugins/fleet-core/scripts/fleet_commons/models.json` with `execution_classes`, `scalar_efforts`,
`root_orchestration_profiles`, and `schema_version`, matching Codex's authoritative version-2 shape.
Add a **sibling** resolver `resolve_for_runtime(work_shape, runtime) -> {model, effort, fallbacks,
workspace_boundary}` in `tier_resolver.py`. Add a per-vendor **argument adapter** mapping the
resolved `{model, effort}` to each CLI's actual flags, since the `agent` wrapper passes tool
arguments through rather than normalising them.

**Why.** Tier routing is the reason the plugin exists (operator's position, recorded), and the
authoritative mapping form exists only on the Codex side today.

**Files.** `plugins/fleet-core/scripts/fleet_commons/models.json`,
`plugins/fleet-core/scripts/fleet_commons/tier_resolver.py`,
`plugins/fleet-core/references/tier-palette.md`, plugin release surfaces per repo CLAUDE.md.

**Watch for.** Do **not** port `lineage_models` / `lineage_efforts` as the live router (KTD7); the
Codex file labels them compatibility data for existing consumers, and their `gpt-5.5` versus
`gpt-5.6-sol` difference is expected, not drift to resolve. Do **not** change `resolve()`'s
signature: twelve files reference `tier_resolver`, including `team_emitter.py`, which wraps
`resolve()`, and `tier_defaults.py:71`, which calls it positionally. Claude's existing `models` /
`efforts` keys stay as the Claude vocabulary; `tier_palette.py` derives `MODELS` / `EFFORTS` from
them and `tests/test_tier_vocab_single_source.py` asserts their contents.

**Test scenarios** — `tests/test_fleet_core_lineage_models.py`:
existing `models`/`efforts` readers are unaffected by the added keys; the twelve existing
`tier_resolver` call sites are unaffected by the new sibling function; a work shape resolves to
different concrete models for the `claude` and `codex` runtimes; each of the six CLIs resolves to a
concrete `{model, effort}` and a correct argument vector; an unknown work shape raises rather than
defaulting; an unknown runtime raises; `fallbacks` are returned in declared order.

**Suggested vendor/tier.** `claude` opus/high — schema judgment with cross-repo consequences.

### U2. Plugin scaffold and the register

**What.** Create `plugins/orchestrate/` by copying the shape of a current skills plugin
(`house-style` or `saga`). Define the register: a flat JSON document **per run**, one row per
child plus one for the mirror and one for the subscriber. Implement atomic read/write (temp
file plus rename) at **`~/.orchestrate/registers/<run_id>.json`** (relocatable by
`ORCHESTRATE_REGISTER_DIR`). The retirement archive is
`.orchestrate/runs/<run-id>/register-final.json` **in the repository**. Add `.orchestrate/` to
this repository's `.gitignore`. Every decision and mutation API requires `run_id`.

**Register columns.** Identity: `id`, `run_id`, `agent`, `vendor`, `model`, `effort`.
Substrate: `herdr_session`, `workspace_id`, `tab_id`, `pane_id`, `cwd`. Work: `task`,
`work_shape`, `scope`, `artifact_path`, `predicate`, `integration_mode`, `destination`.
Lifecycle: `phase` (`planned` → `launching` → `launched` → `ready` → `working` → `verified` →
`reaped`), `expected_state`, `observed_state`. Time: `dispatched_at`, `deadline` or
`max_quiet_seconds`, `last_event_at`. Accounting: `tokens_observed`, `tokens_reserved`.

**Why.** The register is the whole state model (KTD5) and the Claude↔Codex handoff seam (R12).
Revision 1 omitted the substrate, time, and accounting groups, which made U3's subscriptions, U4's
reaping, U7's hang detection, U6's spend gate, and U10's handoff all unimplementable.

**Files.** `plugins/orchestrate/.claude-plugin/plugin.json`,
`plugins/orchestrate/skills/orchestrate/SKILL.md`,
`plugins/orchestrate/skills/orchestrate/scripts/register.py`, `.claude-plugin/marketplace.json`,
`.gitignore`.

**Watch for.** Do **not** use `tools/create-plugin.sh`: it emits `src/main.py`, `tests/test_main.py`,
`docs/`, and a manifest keyed `"id"` with `"main": "src/main.py"` — the CLI-plugin layout — while
`scripts/sync_marketplace.py:51` indexes `plugin_json["name"]` and would raise. The live register
is **one document per run**, addressed by `run_id` in an orchestrator-owned host-local
directory. Rows are retired to `.orchestrate/runs/<run-id>/register-final.json` in the
repository when a run completes, and the per-run secret is deleted so the id does not inherit
the retired run's authentication identity.

**Test scenarios** — `tests/test_orchestrate_register.py`:
a fresh register initialises with a schema version; a row round-trips every column above; an atomic
write leaves no partial file when interrupted; an unknown key **nested inside a child row** is
preserved on write, not only an unknown top-level key (C4); a schema version the code does not
support halts with a receipt and mutates nothing (C3); two sequential writers do not lose the first
writer's row; retiring a run moves its rows and leaves other runs intact.

**Suggested vendor/tier.** `claude` sonnet/medium — bounded, well-specified, testable.

### U3. herdr event client, the subscriber, and catch-up

**What.** Three things. **(a)** A client that opens `~/.config/herdr/herdr.sock`, sends
`{"id", "method": "events.subscribe", "params": {"subscriptions": [...]}}`, and dispatches decoded
events. **(b)** The **subscriber**: a single-purpose process the orchestrator spawns, which holds
that socket across turns and wakes the orchestrator by `agent.prompt` into its pane (KTD3). It
carries a register row so its own death is a visible divergence. **(c)** The **catch-up pass**
(KTD12), run at startup and after every reconnect: read the live herdr snapshot for every registered
handle, compare expected against observed, and re-evaluate run-bound artifacts and predicates.

**Why.** This is the wake mechanism, and without (b) nothing holds the subscription between turns
while without (c) every reconnect silently loses whatever happened during the gap.

**Verified contract details** — these cost a round each during discovery, so they are recorded.
**Subscribe request types are dotted; broadcast envelope names are underscored, and they are not
interchangeable**: subscribe with `tab.closed`, `pane.exited`, `pane.output_matched`; receive
`tab_closed`, `pane_exited`. `pane.output_matched` is a `SubscriptionEventKind`, not one of the 26
`EventKind` values, and its subscribe object requires `type`, `pane_id`, `source`, **and** `match` —
not `type` and `pane_id` alone. The API spells the read source `recent_unwrapped` (underscore) where
the CLI uses `recent-unwrapped` (hyphen). `match` is a tagged enum
`{"type": "substring"|"regex", "value": ...}`, not a bare string. A successful subscribe replies
`{"result": {"type": "subscription_started"}}`.

**Run sentinels.** `pane.output_matched` searches existing pane content, so a newly dispatched child
can match text already in scrollback and be classified ready or complete before it reacts. Every
readiness and completion interaction injects a unique `run_id`-and-`child_id` sentinel, and the
match requires an output revision later than the pre-dispatch baseline recorded in the register.

**Files.** `plugins/orchestrate/skills/orchestrate/scripts/herdr_events.py`,
`plugins/orchestrate/skills/orchestrate/scripts/subscriber.py`,
`plugins/orchestrate/references/herdr-event-api.md`.

**Test scenarios** — `tests/test_orchestrate_herdr_events.py`:
a subscribe request serialises with the dotted types, checked against a schema fixture the unit
commits under `plugins/orchestrate/tests/fixtures/`, captured from `herdr api schema --json` at
build time and carrying the `Subscription`, `SubscriptionEventKind`, `EventKind`, and `OutputMatch`
definitions — never against hand-written strings; an underscored subscribe type is
a hard error, not an ignored unknown kind; a malformed subscription is reported rather than silently
dropped; `pane.output_matched` with a regex decodes `matched_line`; a sentinel present in
pre-dispatch scrollback does **not** satisfy the match; a socket close mid-stream triggers reconnect
**and** a catch-up pass; a child that exits during a disconnect is detected by catch-up rather than
lost; an event for an unregistered `pane_id` mutates no row and is reported once as a diagnostic; a
socket that does not exist fails with an actionable message.

**Suggested vendor/tier.** `codex` gpt-5.6-sol/high — protocol work with a precise written contract.

### U4. Session lifecycle — write-ahead launch, readiness, reap

**What.** Launch children through the `agent` wrapper on its control-only path (dry-run preview,
confirm `cwd` and workspace, `--no-focus`, explicit model and effort from U1's adapter). Write the
register row **before** the launch side effect, following `planned → launching → launched → ready`,
with a run-bound unique task label written first so a crashed launch is recoverable by discovery.
Record `workspace_id`, `tab_id`, and `pane_id` from the wrapper's return immediately. Confirm
readiness **by interaction**: dispatch, then require an observed sentinel within a bounded window.
Provision the landing model for mutating children (below). Reap on verified completion, recording
the transition before closing the tab.

**Landing model.** Mutating children get a git worktree; read-only children do not (the accepted cut
covers read-only work only). `outcome_worktrees.py` is not a drop-in — it manages autonomous
sub-outcomes and deliberately leaves plain leaves in the ambient worktree — so U4 either adapts it
or provides an equally bounded adapter, recording `destination` and `integration_mode`
(`branch` | `path` | `none`) per row. Scope is **enforced**: translate the declared scope into each
CLI's permission flags where they exist, and compare the pre-dispatch baseline against final changed
paths before completion.

**Why.** Launch success is not readiness (a child can sit on a trust prompt); a reap the watcher has
no record of raises a false alarm asserting the opposite of the truth; a crash between the launch
and the register write orphans a child and duplicates it on resume; and a recorded scope that
nothing enforces lets two mutating children collide in one checkout with both artifacts passing.

**Files.** `plugins/orchestrate/skills/orchestrate/scripts/session_lifecycle.py`,
`plugins/orchestrate/references/substrate-contract.md`.

**Watch for.** Reap is not to be exercised on real work until U5's integration gate lands.
`--no-focus` alone does not mean "launch and return" — the control-only path is what returns without
attaching. Per-vendor launch flags differ and come from U1's adapter, not from invention here.

**Test scenarios** — `tests/test_orchestrate_session_lifecycle.py`:
the register row and run label are written before the launch call, proven by a launch that raises;
a crash after launch and before the identifier write is recovered by discovering the run label
rather than by launching a duplicate; a launch that reports success but never emits its sentinel is
classified not-ready, not running; a child blocked on a trust prompt is detected via content and
surfaced, never dispatched into; a mutating child gets a worktree and a read-only child does not; a
child that writes outside its declared scope fails the boundary check even when its predicate
passes; a reap writes the transition before closing the tab; a child that vanishes without a
recorded reap raises, while one that vanishes after a recorded reap does not; readiness never
consults `agent_status` alone.

**Suggested vendor/tier.** `claude` opus/high — this is where the substrate lies, and judgment about
wrong signals is the unit's substance.

### U5. Completion — predicate, run identity, settlement, integration, depth

**What.** Evaluate a child's validity predicate: a bounded mechanical check declared as a **typed,
closed schema** — a fixed argument vector rather than shell text, with time and output limits and a
predicate digest captured before dispatch — run **inline by the orchestrator**. Bind the artifact to
this dispatch by a run-specific receipt carrying the artifact path and a content digest. Require the
artifact to be **settled**: children write to a temporary path and rename into place, and the
predicate accepts only the renamed path. Require integration to the recorded `destination` to be
verified before the child is reaped, per its `integration_mode`, including an explicit `none` mode
for read-only artifacts. For **judgment-shaped** work, additionally require a blind depth sample by
an independent verifier session, recording verifier identity, sampled claims, evidence locations,
and disposition.

**Why.** Evidence is the highest-severity failure category, and each sub-requirement closes a
concrete defect found by adversarial review: a stale artifact satisfying the predicate; a child
weakening the test that certifies it; a predicate passing on a half-written file; verified work
discarded when a worktree is reaped before the change lands; and a review with every required
heading that misses the decisive defect while all visible gates stay green. Brainstorm R14 was
retained, narrowed to judgment work, and revision 1 dropped it without a deferral note.

**Files.** `plugins/orchestrate/skills/orchestrate/scripts/completion.py`,
`plugins/orchestrate/references/predicates.md`.

**Test scenarios** — `tests/test_orchestrate_completion.py`:
an artifact from a previous run with a different run id does not satisfy the predicate; a predicate
declared as shell text is rejected by the schema; a predicate whose script or whose **dependency
closure** lives inside the child's write scope is rejected before evaluation; an artifact written
directly rather than renamed into place is not settled and fails; a truncated but syntactically
valid artifact fails rather than passing; reaping is refused while the recorded destination is
unchanged under `branch` or `path` mode, and permitted under `none`; a judgment-shaped child cannot
reach verified on mechanical coverage alone; a predicate that errors, hangs, or exceeds its output
limit is a failure, never a pass; a passing predicate on a settled, correctly-bound artifact reaps
cleanly.

**Suggested vendor/tier.** `claude` opus/high — the highest-severity requirement in the plan.

### U6. Planning, routing, admission, and accounting

**What.** The judgment step: given an outcome, decide the split into children, and for each one its
agent, vendor, model, effort, scope, artifact, predicate, and integration mode. Resolve tier from
work shape via `tier_policy.json` and U1's `resolve_for_runtime`, falling back through the ordered
`fallbacks` when a vendor is unavailable (R8). Enforce **per-vendor** and aggregate work-in-progress
bounds with register-owned admission: active-state counting, an atomic slot reservation, a release
rule, and defined restart behaviour. Enforce the spend ceiling from **observed** actuals: record
`tokens_observed` per child by scraping each CLI's own usage line via `pane.output_matched`, and
where a vendor exposes none, consume the declared `tokens_reserved` worst case and fail closed. Show
the plan to the operator before any child launches.

**Why.** Routing across models and vendors is the reason the plugin exists. Revision 1 cited
`concurrency_policy.py` and `cost_ceiling_tokens` as if they enforced R10 and R9; the first defines
three aggregate limits whose enforcer was deleted with `lease_broker`, and the second declines to
engage when `actual_tokens` is `None`, which it always would be.

**Files.** `plugins/orchestrate/skills/orchestrate/scripts/planning.py`,
`plugins/orchestrate/skills/orchestrate/scripts/admission.py`,
`plugins/orchestrate/references/routing.md`.

**Watch for.** `concurrency_policy.py` supplies normalized defaults only; saga's
`concurrency_governor.py` resolves and chunks cohorts and is the real dependency if one is reused.
Neither queues children.

**Test scenarios** — `tests/test_orchestrate_planning.py`:
a judgment-shaped unit resolves to a high tier and a mechanical one to a low tier; the same work
shape resolves to different concrete models for different runtimes; an unavailable preferred vendor
falls back in declared order and records the substitution; an operator-declared vendor preference
overrides the work-shape default and is recorded as explicit; exceeding a **per-vendor** bound queues
even when aggregate capacity remains; a slot reservation survives restart; a child whose vendor
reports no usage consumes its declared reservation; reaching the spend ceiling halts and reports;
missing telemetry fails closed rather than passing; planning never launches a child.

**Suggested vendor/tier.** `grok` or `codex` high — routing logic with clear inputs and outputs;
good candidate for a non-Claude vendor, which also exercises the multi-vendor path.

### U7. The mirror and the operator channel

**What.** A persistent paired session for the orchestrator's own unbounded work — synthesis,
comparison, bulk reading. Returns distilled conclusions only, within a declared byte bound. Holds a
register row with the same temporal columns as any child. Never evaluates a predicate and never
addresses the operator. Context is managed deliberately (compact or clear on the orchestrator's
instruction). Mirror requests are non-blocking: an outstanding request must not prevent the
orchestrator answering the operator.

**Why.** The top failure across the corpus is the operator channel dying under supervision load.

**Files.** `plugins/orchestrate/skills/orchestrate/scripts/mirror.py`,
`plugins/orchestrate/references/operator-channel.md`.

**Watch for.** Hang detection needs a clock: a hung mirror's expected and observed states agree, so
divergence is only detectable as `last_event_at` exceeding `max_quiet_seconds`. The
answerable-while-busy property cannot be established by a unit test if the skill blocks
synchronously; it is proven in U8's integration test and again in the Phase 1 live gate.

**Test scenarios** — `tests/test_orchestrate_mirror.py`:
a predicate evaluation request routed to the mirror is refused (KTD6); a mirror return exceeding the
declared distillation bound is rejected rather than absorbed; the mirror has a register row from
creation; a mirror that stops emitting for longer than `max_quiet_seconds` raises divergence; a
mirror request is dispatched without blocking the caller.

**Suggested vendor/tier.** `claude` opus/high — the channel-protection invariant is subtle.

### U8. Composition — the orchestration control flow

**What.** The unit that makes the previous six into a product. Own the control flow that persists an
approved plan, launches children with U4's write-ahead ordering, spawns and supervises the
subscriber, receives injected wakes, calls U5's completion, advances queued children under U6's
admission, supervises the mirror, and resumes after orchestrator or subscriber death. Define the
Phase 1 acceptance gate as a named end-to-end scenario with an evidence receipt.

**Why.** Revision 1 had no owner for this: U2 created the skill, U3–U7 added isolated modules, and
the surface unit added only a loader. Seven green module suites could land with no working
orchestrator, and the operator-channel property the mirror exists to protect could fail with a fully
green suite.

**Files.** `plugins/orchestrate/skills/orchestrate/SKILL.md` (the control flow it directs),
`plugins/orchestrate/skills/orchestrate/scripts/runner.py`,
`plugins/orchestrate/references/phase-1-acceptance.md`.

**Test scenarios** — `tests/test_orchestrate_composition.py`:
a fake-herdr integration test traverses approved-plan → launch → subscribe → event → predicate →
integrate → reap → next child; an orchestrator restart mid-run resumes from the register and the
catch-up pass without duplicating a child; a subscriber death raises divergence and is respawned; a
mirror request outstanding while an operator message arrives is answered or explicitly parked, with
an observable receipt; the four R1 argument forms each produce a plan.

**Phase 1 gate.** Dogfood on one real, unrelated task with at least two children on different
vendors, at least one mutating and one read-only, and one deliberate mid-run orchestrator restart.
Pass criteria: no child lost, no duplicate launched, no false completion, the operator answered
while the mirror was busy, and a spend figure recorded. Evidence lands at
`.orchestrate/runs/<run-id>/`. A failure here blocks Phase 2.

**Suggested vendor/tier.** `claude` opus/high — this is the integration judgment unit.

### U9. Claude surface and `/outcome` deprecation

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
longer contains the declared orchestration-intent vocabulary — enumerated in the test, not left to
judgment — and does name `/orchestrate`; `/outcome`'s skill and scripts are untouched; the
marketplace entry validates.

**Suggested vendor/tier.** `claude` sonnet/medium — mechanical, well-specified.

### U10. Codex port and same-host cross-runtime round-trip

**Phase 2 — does not start until U8's Phase 1 gate passes.**

**What.** Port the plugin to `infiquetra-codex-plugins` as a skills-only plugin with a
`.codex-plugin/plugin.json`. Port `intent_envelope.py` Claude→Codex (companion C7; that repo's
`fleet-core` has none). Add the declared portable subset to that repo's `models.json` while keeping
`execution_classes` authoritative there. Apply the same `/outcome` deprecation (17 outcome scripts
live on that side). Prove interop with a live **same-host** round-trip in both directions.

**Why.** Starting an orchestration under one runtime and resuming under the other is the stated
requirement, and the lossy-write failure is directional so a one-way test would miss it.

**Files.** In `infiquetra-codex-plugins`: `plugins/orchestrate/**`,
`plugins/fleet-core/scripts/fleet_commons/models.json`,
`plugins/fleet-core/scripts/fleet_commons/intent_envelope.py`,
`plugins/saga/skills/outcome/**` description surface, `.agents/plugins/marketplace.json`.

**Operating constraint.** When Claude Code works in that repository, its `plugins/` directory is
the artifact under repair, never session tooling. Its `saga.py`, validators, and renderers must not
be invoked to drive the session.

**The round-trip procedure** — written as a checklist, because the acceptance is an observation and
not a test: same herdr server and workspace; runtime A launches one child and records its
`pane_id`; A flushes the register and pauses, dropping its subscription; B is launched with an
explicit resume invocation; B re-subscribes to the recorded `pane_id`, observes the running child,
evaluates the predicate, and reaps; evidence lands under `.orchestrate/runs/<run-id>/`; then repeat
in the reverse direction. Run in a throwaway repository, with an explicit cleanup rule.

**Test scenarios** — `tests/test_orchestrate_cross_runtime.py` (fixture conformance only, both
repos): a register written by Claude is read by Codex with every field intact; the reverse holds; a
field nested in a child row, written by one runtime and unknown to the other, survives a write by
the other (C4); a `schema_version` neither supports halts with a receipt. **The live round-trip is
the checklist above, not a pytest case.**

**Suggested vendor/tier.** `codex` gpt-5.6-sol/high, working in the Codex repository — the port
is built by the runtime it targets.

## Scope Boundaries

**Out of scope — not built, so that adding them later is a decision rather than drift.**

- A DAG or graph engine. The register plus a future `blocked_by` column covers it; `/outcome`
  exists if a real DAG appears.
- A reconcile **loop**. `/outcome` already implements level-triggered reconciliation. KTD12's
  catch-up pass is edge-triggered — once per reconnect, never on a schedule.
- A **general-purpose** daemon with its own state, lifecycle, or product surface. The subscriber
  (KTD3) is single-purpose, spawned by the orchestrator, and carries a register row like any child.
- Leases, fencing, and expiry (KTD8).
- A cockpit or dashboard. Aggregation into the conversation replaces it; a surface to go *look at*
  reintroduces the failure this design targets.
- A notification protocol of our own. herdr already provides one; we consume it.
- Automated per-vendor quota discovery. The operator supplies quota state; capacity routing uses the
  tier policy's ordered `fallbacks`.

**Deferred to follow-up work.**

- **Cross-machine handoff** (KTD13). Needs host identity per row, a register transport with a
  conflict rule, and remote herdr routing. Deferred as a decision, not dropped.
- **The Headroom proxy guard.** `headroom/proxy/handlers/anthropic.py:2150` tests
  `provider_name == "anthropic"`, which labels the *protocol spoken* rather than the *upstream
  answering*, so Anthropic-protocol local models (Muse, Ollama, DeepSeek via Claude Code as
  harness) receive a Claude-only capability and fail with HTTP 400. Third-party package; fixing it
  would unlock those routes but is not a dependency — native CLIs work today.
- **herdr detector coverage.** `herdr integration install` lists neither `muse` nor `agy`. Closing
  those gaps improves the operator's sidebar, which has no predicate to fall back on.
- **`fleet-core` convergence beyond the routing tables.** Nine Claude-only and four Codex-only
  modules remain; only the tier mapping and `intent_envelope` are required here.
- **Codex skill bodies referencing Claude syntax.** That repo's `SKILL.md` files say `/plan` where
  a Codex operator would type `$saga:plan`.
- **`tools/create-plugin.sh` modernisation.** It emits an obsolete shape (U2). Fixing it is separate
  work.
- **`/outcome` cull.** Deprecated here, deleted later, on a condition the operator sets after real
  use.

## Risk Analysis & Mitigation

**The substrate changes under us.** herdr detection behaviour has shifted on past upgrades, 21 of 22
detectors are upstream, and neither the herdr binary nor the `agent` wrapper is versioned by this
repository. *Mitigation:* KTD4 — content subscriptions rather than detector state — plus U3's
serialisation test against a committed `herdr api schema --json` excerpt, and a re-run of the
read-only schema and wrapper checks immediately before implementation.

**A cited module declares but does not enforce.** Review found three instances: the spend gate
declines to engage without telemetry nobody produced, `concurrency_policy.py` holds limits whose
enforcer was deleted with `lease_broker`, and `events.subscribe` works while nothing stayed
subscribed. *Mitigation:* every reuse claim in this plan names its **consumer**, not just the module;
U6 and U3 own the enforcing halves explicitly.

**The dogfood biases the design.** This session drives the build and is also the thing being
replaced. *Mitigation:* friction is recorded as evidence rather than resolved silently, and U8's
Phase 1 gate must pass on unrelated real work before Phase 2 begins.

**`models.json` convergence breaks existing readers.** U1 touches a file other components read, and
twelve files reference `tier_resolver`. *Mitigation:* additive keys only, a sibling resolver rather
than a signature change, existing readers and call sites covered by test.

**Scope re-expansion.** Two adversarial reviewers pushed to cut roughly a third of the requirements,
including the tier routing that motivates the work. The operator rejected those cuts with reasons
recorded in the brainstorm. *Mitigation:* the Scope Boundaries section above is the guard; adding
anything from the not-built list requires an explicit decision.
