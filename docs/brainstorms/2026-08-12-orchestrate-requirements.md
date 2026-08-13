# Requirements: `orchestrate` — operator-driven multi-agent orchestration

- **status:** requirements, pre-plan
- **date:** 2026-08-12
- **evidence base:** 552 agent sessions (2026-08-04 → 2026-08-12), 100% proof-verified read;
  243 distinct coordination failures across 477 session-occurrences; 18 first-hand findings from
  running the evidence pass itself as a live orchestration
- **supersedes in intent:** `/outcome` (see R2, R3)

---

## 1. What this is, in one paragraph

Jeff runs a workflow by hand: open several agent sessions in a terminal multiplexer, give each a
piece of a larger goal, keep track of what they're doing, and pull their answers back together.
It works, and it breaks in consistent ways. `orchestrate` is that workflow, codified. It takes a
desired outcome — an issue, a parent issue, a prompt — decides how to split it across real agent
sessions on multiple vendors, keeps one conversation with the operator, and closes the loop when
the work lands.

**The verb is the product.** `/outcome` named the noun, which forced every piece of work to be
shaped as a complete outcome graph before anything could start. That is the overengineering the
operator felt. Here the outcome is an *argument*, and the shape is discovered during planning.

---

## 2. Why now — what the evidence says

Eleven miner sessions read 552 transcripts across Jeff's Claude, Codex, and company-account
histories. Every session's read is proven by a timestamp taken from inside the file itself, so
coverage is measured rather than claimed.

Failures ranked by **severity**, which is `cost × silence` — what one occurrence takes to undo,
multiplied by how far it presents as success. Deliberately *not* ranked by count:

```
   CRITICAL  evidence      ███████████████████ 51 entries   "verified" that wasn't
   HIGH      boundary      ██████████████      39           work outside the agreed scope
   HIGH      notification  ██████████          27           child couldn't reach the operator
   MED-HIGH  model-routing ███████             20           wrong model, silently
   MEDIUM    session-mgmt  ██████████████████  60           lost / duplicated / forked sessions
   MEDIUM    lifecycle     ██████████          28  (130 occ) ceremony that didn't fit
```

**Lifecycle leads the corpus by raw count — 130 occurrences — and lands near the bottom on
severity.** That is not a contradiction, it is the mechanism: it recurs *because* the operator
objects out loud every single time, which is also why it self-corrects within one round. Evidence
failures do the opposite. A wrong "verified" survives the session that produced it and propagates
into plans, decision logs, and other agents' inputs, because nothing looks wrong.

**This is the organizing principle of the whole design:**

> The operator is already an excellent mechanism for loud failures. Build for the quiet ones.

---

## 3. What `orchestrate` actually is

During design we found that `/outcome`'s own requirements already contain this:

> **R15.** *The runner maintains one durable persistent session + worktree per sub-outcome, naming
> and owning it… the runner caps concurrent worktrees, reaps a sub-outcome's worktree on
> completion/abandon.*

`outcome_worktrees.py` implements the **worktree** half completely. There is no session module at
all, and `outcome_spec.py:678` says so in its own source: *"an execution-session concept the
outcome layer has no."*

So `orchestrate` is not a competitor to `/outcome` and not a second coordinator. **It is the
session half of R15, which never got built** — plus the things that are genuinely new since
(§3.2). This is stated as useful history, not as authority: what is built is what is wanted *now*.

### 3.1 The substrate is settled

```
    ┌──────────────────────────────────────────────────────────┐
    │  ORCHESTRATE          decides WHAT, WHEN, and HOW        │
    │                       (planning, routing, aggregation)   │
    ├──────────────────────────────────────────────────────────┤
    │  agent wrapper  +  herdr                                 │
    │                       does CREATE, COMMUNICATE, DESTROY  │
    │                       (sessions, tabs, panes, state)     │
    └──────────────────────────────────────────────────────────┘
```

`herdr` and the local `agent` wrapper are the substrate and are **not** in scope to build. They
already create sessions, deliver prompts, read output, and close tabs. `orchestrate` never
reimplements those; it decides how they are used.

### 3.2 What is new since the original outcome work

| new | why it matters |
|---|---|
| **Aggregation into one conversation** | The operator talks to the orchestrator, not to a dashboard. `/outcome`'s model is a pull-derived cockpit — "empty surface = healthy," operator as interrupt-handler. That is *monitoring*. This is an *interlocutor*. |
| **Multi-vendor as capacity, not just capability** | Spreading work across Anthropic / OpenAI / Qwen / local models extends total available throughput when one vendor's quota is exhausted. No existing component models per-vendor budget. |
| **Children that are not sagas** | A child may be any agent CLI running any lifecycle, or none. Parts of one lifecycle may be spread across several children. |

---

## 4. The architecture

```
                          ┌───────────┐
                          │ OPERATOR  │
                          └─────┬─────┘
                                │
              ═════════════════════════════════════
                THIS CHANNEL MUST NEVER BLOCK.
                Everything below exists to protect it.
              ═════════════════════════════════════
                                │
                    ┌───────────▼────────────┐
                    │     ORCHESTRATOR       │
                    │     (main session)     │
                    │                        │
                    │  • holds the register  │
                    │  • routes decisions    │
                    │  • aggregates results  │
                    │  • ANSWERS             │
                    │                        │
                    │  does NO work itself   │
                    └───┬────────────────┬───┘
                        │                │
         its own work   │                │  the outcome's work
                        ▼                ▼
                  ┌──────────┐    ┌──────────────────────────┐
                  │  MIRROR  │    │        CHILDREN          │
                  │          │    │                          │
                  │ synthesis│    │  codex   qwen   claude   │
                  │ compare  │    │  muse    agy    opencode │
                  │ verify   │    │                          │
                  │ read     │    │  each: own worktree,     │
                  └────┬─────┘    │  own scope, own artifact │
                       │          └────────────┬─────────────┘
                       │                       │
                  distilled                 artifacts
                  conclusions               on disk
                       │                       │
                       └───────►  register  ◄──┘
```

### 4.1 The mirror, and the failure it prevents

The top failure across 552 sessions is not scope creep or wrong models. It is **the operator
channel dying under supervision load.** Verbatim, from sessions where it was never answered:

> *"Can we use herdr to open up couple other sessions? maybe we need three tabs for codex, claude,
> antigravity to run those proofs in parallel? thoughts?"*

> *"where do we stand on this... the whole session is very, very long"*

```
   TODAY                              WITH A MIRROR

   operator ──?──► orchestrator       operator ──?──► orchestrator
                        │                                  │  answers immediately
                   (doing work)                            ▼
                        │                              ┌────────┐
                   ...busy...                          │ MIRROR │ ← work happens here
                        │                              └────────┘
                    no answer                              │
                        │                            distilled result
                   operator gives up                       │
                   and checks tabs manually          operator informed
```

The rule "the orchestrator must not do work" is insufficient on its own, because work genuinely
must happen — synthesis, comparing two children's answers, verifying an artifact. A rule with no
home for that work is a rule that gets broken. The mirror is the home.

**The limit, stated so it is designed for rather than discovered:** the mirror protects *time*,
not *context*. The orchestrator still reads what the mirror returns. If the mirror hands back
50 KB, the main session absorbs 50 KB and degrades anyway. Hence R6.

### 4.2 The event substrate — how the orchestrator is woken

`herdr` exposes a **push event API over a unix socket** (`~/.config/herdr/herdr.sock`,
protocol 19). This is the mechanism that makes autonomy possible without a daemon, and it is
verified working rather than assumed:

| capability | status |
|---|---|
| `events.subscribe` — open a stream of filtered events | **verified live** — returns `{"result":{"type":"subscription_started"}}` |
| `tab_created` / `tab_closed` / `pane_exited` — global, need only `type` | **verified live** |
| `pane.output_matched` — fires when a pane's output matches a **substring or regex** | **verified live** — payload carries `matched_line` plus a full `read` of the pane |
| `pane.agent_status_changed` — per-pane, optional `agent_status` filter | in schema; subscribed successfully, no event observed in the test window |
| `events.wait` — block until one matching event, with `timeout_ms` | in schema; not exercised |

26 event kinds exist in total, covering workspace, worktree, tab, and pane lifecycle.

```
   ┌──────────────┐   events.subscribe    ┌─────────────────────┐
   │ ORCHESTRATOR │◄──────────────────────│  herdr socket API   │
   │              │   push, not poll      │  ~/.config/herdr/   │
   └──────────────┘                       └──────────┬──────────┘
          ▲                                          │ observes
          │ woken by                                 ▼
          │                              ┌────────────────────────┐
          └──────── pane.output_matched  │ children: codex, qwen, │
                    tab_closed           │ muse, claude, agy, …   │
                    pane_exited          └────────────────────────┘
```

**Two consequences that shape the whole design.**

**1. The wake mechanism belongs to herdr, not to the host harness.** Any process that can open a
unix socket can subscribe — Claude Code, Codex, or a shell script. Autonomy is therefore
runtime-portable *by construction*, and does not depend on a per-runtime background-task feature.

**2. `pane.output_matched` bypasses the per-agent lifecycle detectors entirely.** It matches
**content**, never `agent_status`, so it is unaffected by a broken or missing detector. This
matters because detectors are wrong in vendor-specific ways: `agy` reports `idle` while working;
`muse` via its adapter reported settled from launch through completion, with `state_change_seq`
never advancing. A content subscription is immune to all of it.

> **The rule this establishes:** subscribe to what a child *emits*, not to what a detector *says
> about* the child. Detector accuracy becomes a nice-to-have rather than a dependency.

---

## 5. The state model is one table

Not a graph. One row per child:

```
┌──────┬────────┬────────┬──────────┬────────┬───────────┬──────────┬────────┬──────────┬────────┐
│ id   │ agent  │ vendor │ model /  │ task   │ scope     │ artifact │ run    │ expected │ observ │
│      │        │        │ effort   │        │           │ +predicate│ id    │          │        │
├──────┼────────┼────────┼──────────┼────────┼───────────┼──────────┼────────┼──────────┼────────┤
│ c1   │ codex  │ openai │ sol/high │ review │ repoA/src │ r1.md    │ 7f3a   │ running  │ working│
│ c2   │ qwen   │ qwen   │ max      │ survey │ repoA(ro) │ s1.md    │ 7f3a   │ running  │ blocked│ ←alarm
│ c3   │ claude │ anthr. │ opus/high│ design │ docs/**   │ d1.md    │ 7f3a   │ reaped   │ gone   │  ok
│ M    │ mirror │ anthr. │ opus/high│ —      │ read-only │ —        │ 7f3a   │ running  │ working│
└──────┴────────┴────────┴──────────┴────────┴───────────┴──────────┴────────┴──────────┴────────┘
```

The **`run id`** column is what binds an artifact to *this* dispatch (R14a) — without it a
leftover file from an earlier run satisfies the predicate and the child is reaped before doing
anything. The **mirror gets its own row** (R6c): it is a supervised entity like any other, and the
one whose silent failure is hardest to notice.

This single structure answers every top failure category, which is the argument for not building
anything larger:

```
  boundary      (39) ──► the `scope` column. out-of-scope is a row-level check.
  session-mgmt  (60) ──► the table IS the session list. nothing is lost or forgotten.
  evidence      (51) ──► `artifact + predicate`. "done" is never a claim.
  notification  (27) ──► `expected` vs `observed`. alarms fire on DIVERGENCE only.
  model-routing (20) ──► `vendor` and `model` are columns, so quota balancing is a query.
```

**Growth path, deliberately not built now.** The one thing a table cannot express is *"child B
needs child A's output."* When that pressure arrives, the fix is a single `blocked_by` column — at
which point the table is a minimal DAG. Cyclic structures, if ever needed, follow the same route.
The structure is chosen during planning, and only real pain justifies a new one.

---

## 6. Requirements

### A. Surface

- **R1.** The command is a verb: `/orchestrate <outcome>`, where `<outcome>` is an issue number, a
  parent issue, a requirements document, or a prose prompt. Nothing must be decomposed before
  invocation.
- **R2.** `/outcome` is deprecated **mechanically, not editorially**: its `description:` frontmatter
  — the field that actually drives command selection — is rewritten so it no longer matches
  orchestration intent and names `/orchestrate` as the replacement. A deprecation banner in prose
  does not satisfy this requirement, because prose does not affect selection.
- **R3.** A **cull condition** is recorded when `/outcome` is deprecated: a falsifiable statement of
  what must be true to delete it (e.g. *N real outcomes driven by `orchestrate` with zero
  fallbacks*). Not a date. Without this, deprecation is permanent by default — this repository
  already grew from 7 plugins to 12 without the count ever being revisited.

### B. The operator channel — highest severity

- **R4.** The orchestrator session performs **aggregation and conversation only**. It routes,
  decides, records, and answers. It does not perform substantive work in the operator's channel.
- **R5.** The orchestrator has a **mirror**: a paired session that performs the orchestrator's own
  work — synthesis, comparison, verification, bulk reading. The mirror is distinct from children:
  *children do the outcome's work; the mirror does the orchestrator's work.*
- **R6.** The mirror returns **distilled conclusions, never raw material**. This is a mechanical
  contract, not an aspiration, because it is the requirement that silently erodes.
- **R6a.** The mirror is **persistent for the life of the orchestration**, for prompt-cache benefit
  and continuity of context. Its context is a **managed resource**: the orchestrator may direct it
  to compact or clear, and does so deliberately rather than letting it fill. A mirror that has
  silently degraded is worse than no mirror, because the orchestrator will still believe its
  answers.

- **R6b — the validity predicate never runs in the mirror.** It is a bounded mechanical check —
  a file test, a required-section grep, a schema parse, a test exit code — and the orchestrator
  runs it **inline**, which R7 already permits because its output is bounded by construction.

  > *Raised by adversarial review, and correct.* Routing the predicate through the mirror makes
  > verification a **claim** again: the mirror reports PASS, the orchestrator never sees the bytes
  > and cannot re-check, and the evidence-failure class — the highest-severity category in the
  > corpus — reappears one layer up with no second reader. The mirror does unbounded *reading*;
  > it does not do *deciding*.

- **R6c — the mirror has a row in the register.** It is the only long-lived session that would
  otherwise have no liveness representation, and it is the one whose failure is least visible: if
  the mirror hangs, every child still looks healthy while the operator channel is dead — the exact
  failure the mirror exists to prevent.
- **R7.** Operator requests to the orchestrator follow **strict-with-a-named-exception**: work goes
  to the mirror by default; the exception list is explicit, small, and written down. Anything not
  on the list goes to the mirror even when it looks trivial.
- **R8.** An operator question is **never silently dropped**. It is answered, or explicitly parked
  with a reason. Evidence: the same unanswered question recurs verbatim across four sessions in the
  corpus.
- **R9.** The mirror never speaks to the operator. One voice, or the channel problem returns
  wearing a different hat.

### C. Done means an artifact

- **R10.** Every child declares its **artifact path** at dispatch, before it starts.
- **R11.** Every child declares a **validity predicate** the orchestrator can run — a required
  section, a schema check, a parse, a test. Existence and file size are not evidence.
- **R12.** "Done" means **the predicate passes**. Never a child's claim, never a lifecycle state.
  Evidence: a 24 KB ledger that was byte-indistinguishable from a valid one and failed verification;
  and a complete, verified ledger produced while the substrate still reported the session `working`.
- **R13.** **Verify before reap, always.** A session is closed only after its artifact passes. This
  is not hygiene: recovering a defective artifact from a live session cost one prompt and one
  minute; the same recovery after reaping would have cost an 80-minute re-run.
- **R14.** For judgment work, coverage verification is **not sufficient**. Coverage (mechanical,
  total) proves a source was opened; depth (sampled, blind, independent) proves it was understood.
  Evidence: all miners passed coverage at 100%, and re-reading the sessions they had marked
  "nothing" recovered 17 real findings from 123 files — including the single highest-recurrence
  boundary finding in the entire corpus.

The following four were raised by independent adversarial review and are kept regardless of any
scope decision, because each is a concrete defect rather than a matter of ambition.

- **R14a — a predicate must be bound to *this* dispatch.** Completion requires a run identity or a
  pre-dispatch baseline. Without one, an artifact left over from an earlier run already satisfies
  the check, and a freshly dispatched child is marked done and reaped before it has done anything.
- **R14b — verification runs outside the producer's write scope.** A child that can edit the thing
  that certifies it can certify itself: weaken a test, pass the test. The predicate, and anything
  it depends on, must not be inside the child's mutation scope.
- **R14c — integration precedes reaping.** A child may fix code, pass its tests, and produce a
  valid artifact inside its worktree while the destination branch is untouched. Reaping at that
  point destroys the work. The transition to reaped requires the change to have landed where it was
  meant to land, verified there.
- **R14d — artifacts are read only when settled.** A predicate must not run against a file the
  child is still writing, or it can pass on a truncated artifact and then reap the evidence of the
  truncation.

### D. Boundaries as data

- **R15.** Each child row carries its **own mutation scope**: what it may write, what is read-only,
  what is forbidden. Scope is per-child data, not shared prose.
- **R16.** Scope is enforced **mechanically wherever the substrate allows** — worktree isolation,
  sandbox flags, read-only mounts — and stated explicitly where it cannot be.
- **R17.** Stop conditions are **structured data**, not paragraphs. A child that hits one halts and
  reports; it does not reason its way past.
- **R18.** A child **never escalates its own permissions**, and never receives an escalation without
  an explicit operator decision recorded in the register. Evidence: a delegated session's own
  recommended fix for a blocking prompt was to grant itself broader permissions.
- **R19.** The orchestrator reports progress as **findings confirmed or killed and decisions
  closed** — never as documents written or sessions launched.

### E. Session lifecycle

- **R20.** One **worktree per child**, bounded and lifecycle-managed. Reuse `outcome_worktrees.py`,
  which already implements naming, capping, reaping, and shared dependency installs.
- **R21.** **Launch success is not readiness.** A newly created session may be blocked on a trust
  prompt, a login, or a model selector. Readiness is confirmed **by interaction, not by reported
  state**: dispatch, then require an observable change within a bounded window. A session that does
  not move was not ready, whatever it claimed.

- **R21a — the orchestrator is woken by subscription, never by polling.** It holds an
  `events.subscribe` stream on the herdr socket for the panes it owns. Polling loops are a fallback
  for what the event API cannot express, not the primary mechanism.

- **R21b — subscribe to what a child emits, not to what a detector says about it.** Completion,
  readiness, and blocked-state subscriptions use **`pane.output_matched`** with a per-agent pattern
  wherever a content signal exists. `pane.agent_status_changed` may be used as a supplementary
  hint; it is never the sole basis for a decision.

  This is not pessimism about the substrate; it is arithmetic:

  | | |
  |---|---|
  | detectors herdr ships | 22 agent kinds |
  | locally owned adapters | **1** (`muse-herdr`) |
  | upstream, not ours to fix | 21 — including `agy`, `codex`, `claude`, `qwen`, `opencode` |

  Observed wrong three different ways, by three different vendors, in one day: `agy` reported
  `idle` while working; `claude` via Herdr reported `working` after finishing and writing a verified
  artifact; `muse` via `muse-herdr` reported settled while mid-thought. The errors do not agree
  because there is no reason they should — each detector infers independently.

  Two further pressures make the dependency unsafe rather than merely imperfect: detection
  behaviour can change under a **herdr upgrade the operator did not initiate** (this has happened
  before and is suspected to recur per upgrade), and **the newest vendor always has the
  least-tested detector** — while adding vendors is the point of the tool. Failure probability is
  highest exactly where the value is highest.

  **Improving detectors and adapters is worthwhile and belongs to the herdr integration layer, not
  to this plugin.** `orchestrate` benefits when they improve and must not require it. Content
  subscriptions tell it *when to go look*; the validity predicate (R11, R12) tells it what is true.

  Note that `herdr integration install <agent>` is the supported path for detector coverage, and
  it does not currently list `muse` or `agy` — which is why a hand-built `muse-herdr` adapter
  exists. Closing those gaps improves the operator's own sidebar, which has no predicate to fall
  back on and currently shows a permanently-idle dot for muse.
- **R22.** **Dispatch is not completion.** A blocking wait may be satisfied by the state a session
  was already in. Completion is confirmed against the artifact predicate, or by requiring a
  pre-dispatch state token to advance.
- **R23.** The register distinguishes **a clean exit from an abandonment**. Alarms fire on
  divergence from intent, never on observation alone — otherwise every successful cleanup raises a
  false alarm whose text confidently asserts the opposite of the truth (observed live: a correctly
  reaped session reported as *"not reaped by me, investigate"*).

  > *Refined after surveying the Codex repository.* An earlier draft expressed this as an
  > expected-vs-observed convention. `lease_broker.py` in the Codex `fleet-core` already provides it
  > as a **data structure**: a lease *released* is a clean exit, a lease *expired* is an
  > abandonment, with expiry derived from monotonic renewal rather than a stored status bit.
  > Prefer the structure over the convention — conventions drift, leases do not.
- **R24.** **Reaping is a recorded transition**, not merely an action taken. The record is what
  makes the subsequent absence legible.

### F. Vendors and models

- **R25.** Model and effort are selected per child by **work shape**, reusing `fleet-core`'s
  `tier_policy.json` (judgment → high tier; mechanical → mid; read-only survey → low). The
  **work-shape vocabulary stays vendor-neutral**: a vendor is added by extending the *resolution
  mapping*, never by adding vendor names to the tier vocabulary.

  > *Corrected after surveying the Codex repository.* An earlier draft of this requirement said
  > "extend the palette beyond Anthropic-only," which is the wrong shape. `models.json` in the
  > Codex `fleet-core` already implements the right one — a `lineage_models` table where the tier
  > name (`fable`/`opus`/`sonnet`/`haiku`) is an **abstraction** each runtime resolves to its own
  > concrete model and effort. Adding Qwen or Gemini is a mapping entry, so the tier policy never
  > has to be rewritten when a vendor appears.
- **R26.** Vendor selection considers **remaining quota as well as capability**. Offloading to a
  vendor with budget available is a first-class reason to route there, independent of benchmark
  scores. This is a primary advantage of the tool, not an optimization.
- **R27.** Model and effort are **explicit for every child**. Inheritance is permitted only as a
  recorded, deliberate choice.
- **R28.** Cross-vendor children run on **native CLIs** (codex, qwen, muse, opencode, agy) where
  available. Using Claude Code as a harness for non-Anthropic models is a known-broken path — a
  local proxy adds a Claude-only capability to any request carrying 12+ tools, and its guard tests
  the *protocol spoken* rather than the *upstream answering*, so Anthropic-protocol local models
  fail it. That is a separate fix, not a dependency of this build.

  Native CLIs are the normal case and they work: `codex`, `qwen`, and `muse` all run cleanly as
  children today. `opencode` is model-agnostic and herdr-supported, and is a candidate for reaching
  models that Claude Code cannot host well.

- **R28a — a spend ceiling exists and is enforced.** Routing (R25/R26) can fan children out across
  vendors at high effort; `root_orchestration_profiles` in the Codex catalog already defaults the
  root to `max`. Without a ceiling an orchestration can consume a large budget with no point at
  which anything stops. The envelope's `cost_ceiling_tokens` is the existing field for this and
  should be honoured rather than replaced.

### G. Planning

- **R29.** **Orchestration planning is the one judgment step.** It decides the split, the children,
  their agents and vendors, their scopes and artifacts, and the coordination structure. Everything
  downstream is mechanical.
- **R30.** The plan is **shown to the operator before any child is launched**, and launching is not
  implied by planning.
- **R31.** Work in progress is **bounded and declared** — a maximum number of concurrent children,
  respecting per-vendor concurrency limits. Satisfied by `concurrency_policy.py` in the Codex
  `fleet-core`, whose stated purpose is already *"fleet-wide serialized admission limits shared by
  every runtime"*; admission control and a work-in-progress cap are the same problem.

---

## 7. Deliberately not built

Listed so that adding them later is a decision rather than a drift:

| not building | why |
|---|---|
| A DAG engine | The table plus a future `blocked_by` column covers it. `/outcome` has one if a real DAG appears. |
| A reconcile loop | Level-triggered reconciliation is the right idea and `/outcome` already implements it. Do not rebuild beside it. |
| ~~Cross-runtime portability contract~~ | **Reversed.** The operator requires Claude↔Codex handoff, so the register *is* a cross-runtime artifact. Reuse `outcome-cross-runtime`'s proven **pattern** — versioned schema, compatibility halt on unknown versions, preserve-unknown-fields — not its machinery. |
| Seven new `IntentEnvelope` fields | `backends_permitted` already exists and already satisfies "no team-execution under orchestrate". Extend only when a requirement fails without it. |
| A cockpit / dashboard | Aggregation into the conversation replaces it. Adding a surface to go *look at* reintroduces the failure this design targets. |
| ~~A notification protocol~~ | **Reversed — but by adoption, not by building.** herdr already provides one (`events.subscribe`, verified live in §4.2). We consume it; we do not invent one. The artifact on disk remains the *truth*; the event is the *wake*. |
| A background daemon or controller process | Not needed. `events.subscribe` supplies the wake, so autonomy requires no long-lived process of our own — which was the main argument for a separate controller product. |

---

## 7a. Adversarial review — what was accepted and what was rejected

Reviewed independently by **codex `gpt-5.6-sol` at max effort** and **muse
`muse-spark-1.2-contributor` at xhigh**, neither able to see the other. Both raw reviews are
retained. Dispositions are recorded here because a rejected finding with a reason is worth more
later than a silently dropped one.

### Accepted

| finding | now |
|---|---|
| The mirror running the predicate makes verification a claim again | **R6b** — predicate runs inline |
| The mirror has no liveness representation | **R6c** — mirror gets a register row |
| A predicate can be satisfied by a leftover artifact | **R14a** — run identity |
| A child can weaken the test that certifies it | **R14b** — verify outside the write scope |
| Verified work discarded when a worktree is reaped before the change lands | **R14c** — integration precedes reaping |
| A predicate can pass on a half-written file | **R14d** — settle before reading |
| No spend ceiling anywhere | **R28a** |
| Cross-machine handoff and lease fencing are mutually exclusive as specified | leases, fencing, and expiry **cut entirely** |
| Cross-runtime schema gate is overbuilt | **cut** |
| Worktree per read-only child is unnecessary | **cut** |
| Deprecation ceremony (R3's falsifiable cull condition) is disproportionate | **cut** |

### Rejected, with reasons

**"Nothing wakes the orchestrator; agent sessions run only during turns."** *Factually wrong.*
herdr provides `events.subscribe` and `events.wait` over its socket, verified working in §4.2.
Neither reviewer knew the API existed. This finding had driven a proposal to either build a
separate daemon or reduce the tool to operator-triggered commands; both were abandoned once the
premise was checked. **The lesson is procedural: an external finding with a confident causal claim
still has to be tested against the substrate before it is acted on.**

**"Cut tier and vendor routing" and "cut autonomy; make the operator's turn the tick."** Both
engines applied enterprise-scale scope judgment to a single-operator personal tool. The operator's
position, which governs: routing across models and vendors *is the reason the plugin exists* —
without it this is a tab-opener — and an orchestrator that only acts when asked is the existing
manual workflow with new vocabulary. The operator does not have turns; he checks in when he has
time, and the orchestrator is expected to decide as much as it can in between.

**"Cut the persistent mirror."** Kept, with R6b and R6c applied. The "doubles the supervision
surface" objection holds only if the mirror is an autonomous supervised entity; called
synchronously it is closer to a function call. Its genuine defects were the predicate placement and
the missing liveness row, and both are now fixed rather than avoided by deletion.

**"Cut blanket depth verification (R14)."** Kept, narrowed rather than cut: depth verification
applies to judgment work whose output cannot be checked mechanically, not to every child.

### The reviewer bias worth naming

Both engines independently over-rotated toward "this is too much scope," reaching for
governance appropriate to a large product. A one-person tool has a different threshold: the cost of
a wrong feature is a wasted afternoon, not a migration. **Their defect-finding was excellent and
their scope judgment was not**, and the two should be weighted differently on any future review.

## 8. Questions, answered by the operator

**1. Where does the register live? → A file in the repository.** The reason is interoperability:
start an orchestration under Claude, resume it under Codex. A repo file also gives provenance. See
the [Codex-phase requirements](2026-08-12-orchestrate-codex-phase-requirements.md), where the
register is the handoff seam and `lease_broker.py` is the mechanism.

**2. Is the mirror persistent or per-task? → Persistent, for the life of the orchestrator.** Two
reasons: prompt-cache benefit across repeated work, and context management. The orchestrator may
instruct the mirror to `/compact` or `/clear` when its context fills — meaning **mirror context is
a managed resource, not an accident**, which is a requirement in itself (see R6a).

**3. What is on the R7 exception list? → Recorded below as an initial recommendation**, to be
corrected by use rather than by argument.

**4. How is per-vendor quota observed? → Operator-managed for now.** Most vendor tools expose it,
inconsistently and sometimes not at all. Automating it is separate, later work. R26 therefore
states the *principle* (route for capacity, not only capability) and the operator supplies the
input.

**5. Codex sibling. → Required, and needed before planning.** Both runtimes must be
interchangeable orchestrators over the same substrate. Covered in the companion document.

### R7 initial exception list

The rule that makes this testable rather than a matter of taste:

> **If you do not know the size of the output before you run it, it goes to the mirror.**

`--json` field selection is bounded by construction; `cat file` is bounded only by hope.

| the orchestrator may do inline | must go to the mirror |
|---|---|
| read and write its own register — that *is* its state | read any file whose length it does not already know |
| bounded-output lookups (`gh issue view N --json state`, a session's state, does-path-exist) | any grep or search across a repository |
| launch, prompt, and reap children — routing, not work | read a child's full output, as opposed to its predicate *result* |
| answer the operator from what it already knows | compare two artifacts |
| decide — routing, tier selection, scope assignment | write any document |
| | run tests or builds |

## 9. Open

1. **Where in the repository does the register file live?** It must be runtime-neutral —
   `.claude/` or `.codex/` would fork it by runtime and defeat the purpose.
2. **`fleet-core` has diverged between the two repositories.** `orchestrate` needs `IntentEnvelope`
   (Claude-only) and `lease_broker` (Codex-only), and neither repository currently has both.
3. **Hermes and Antigravity** have plugin repositories on the same lifecycle. Out of current scope,
   but the same interop argument will apply to them.

---

## 9. Provenance

- Pain-point ledger: 243 entries / 477 occurrences, 11 shards, all 100% proof-verified.
- First-hand findings: 18, recorded while running this evidence pass as a live orchestration.
- Notification root cause: traced to `headroom/proxy/handlers/anthropic.py:2150`.
- Charter analysis: the orchestration charter's full ceremony ran in all three live uses and the
  failures happened anyway — the charter's content is largely right, and nothing checks it.
