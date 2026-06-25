---
date: 2026-06-25
topic: operator-outcome-orchestration
focus: an operator-facing outcome-orchestration capability built into the saga plugin — a distinct in-saga OutcomeOrchestrator coordinating a DAG of leaf sagas (reframed from "outcome = saga" after two second opinions), reusing saga machinery + friend plugins as subplot executors, so the operator runs a whole outcome across sessions without manually tracking the DAG
scope: broad
repo: infiquetra-claude-plugins
maturity: idea-ready
---

# Ideation: Operator Outcome-Orchestration for Saga

**Consolidated design brief** — merges two `/ideate` runs (the operator-experience run `ee1f7558`
and the implementation-substrate run `afc929e2`,
[`2026-06-25-outcome-orchestration-saga-ideation.md`](./2026-06-25-outcome-orchestration-saga-ideation.md))
with two independent second opinions (Codex + Antigravity, below) — the latter reframed the spine (see **Architecture reframe**). This is a single **all-or-nothing** design to build
whole — not a phased rollout — feeding `/brainstorm`. Source problem:
[`docs/analysis/2026-06-25-claude-cache-and-orchestration-chatgpt-source.md`](../analysis/2026-06-25-claude-cache-and-orchestration-chatgpt-source.md).

## Grounding Context

**Repo:** an outcome is a **saga-of-subplots** — one saga whose work decomposes into a DAG of
**subplots**; self-similar (a subplot elaborates into its own subplots); the saga + subplots scale
with entry altitude (task → sub-issue → outcome). No new entity — saga, started higher. The DAG
machinery exists but only WITHIN one run (`execution_spec.py`: `dependency_layers()` Kahn `:361`,
per-unit `{model,effort}`, refute-N verifier); a subplot DAG that survives session boundaries does
not. Backends "offered, not vendored" (`operator-choice.md:37`); binding: dead-wiring guard,
HALT-not-degrade, self-modifying-engine gate. Friend plugins (team-execution, mission-control,
deploy, the cc-workflows-ultracode Workflow backend) become per-subplot executors.

**⚠️ Grounding correction (verified mid-run):** `team_emitter.py` EXISTS (`emit_team_structure()` at
`:71`, tested, own CLI). The gap is not a missing file — `recompile_for_tier()`
(`execution_spec.py:708-724`) is downgrade-only and floors team-execution to `emit_inline_baseline()`.
The by-mode dispatch shape already exists, on the wrong path.

**Named repos:** `infiquetra-sdlc` — the Initiative→Objective→Capability hierarchy is *decomposition,
not a DAG* (no `depends_on` edges); board-state vs saga-state are deliberately distinct coordinate
systems. **Context-libraries:** none contributed.

## Topic Axes

A1 saga-of-subplots authoring & cross-altitude scaling · A2 cross-session state & operator cockpit ·
A3 per-subplot execution-tool recommendation (cost lever) · A4 prompt/handoff generation & completion
read-back · A5 friend-plugin participation as subplot executors.

## Architecture reframe — the outcome is a coordinator, not a bigger saga

Two independent second opinions (Codex *soft*, Antigravity *hard*) broke the original "an outcome is just a self-similar saga" premise on a concrete, code-grounded flaw: `saga.py`'s `lifecycle_phase` is a **strictly linear** SDLC path (ideation→plan→work→qa→retro), but an outcome is a **DAG of concurrent subplots** — there is no coherent `lifecycle_phase` for an outcome whose subplot A is in `work`, B in `qa`, and C is blocked in `plan`. A coordinator and a leaf-executor are not self-similar (Antigravity: an outcome is functionally an *Epic* — it produces *completed sagas*; it does not get code-reviewed or scanned on itself).

**Revised spine:** the outcome is a distinct **`OutcomeOrchestrator`** — a COORDINATOR — that is still **built into the saga plugin** and **reuses its machinery** (`execution_spec`'s DAG / Kahn layers / emitters, `recommend_execution_backend()`), but is **not** the linear `Saga` dataclass. It owns the dependency graph, the concurrency locks, and operator-attention routing; the **leaf subplots stay strictly linear sagas** (the executors).

- **Preserved** — the self-similar *operator experience*: enter at any altitude (task / sub-issue / outcome), recursive decomposition, one set of verbs.
- **Dropped** — the self-similar *data structure*: one dataclass for both coordinator and leaf. The leaves are sagas; the outcome is the thing above them.

The 12 components below all stand (they are operator moves) but are now homed in the `OutcomeOrchestrator`, not an overloaded `Saga` — **where any component below says "saga started higher," read "the in-saga `OutcomeOrchestrator`."** The four Antigravity prerequisites (#13–#16) are what make the coordinator safe; the operator-view decision is unaffected.

## The unified design (what we'd build)

The operator drives a whole outcome from an explicit **`/outcome` cockpit** (#3) whose guts are "saga
started higher" — one saga, a DAG of subplots. The cockpit is a **derived projection** over saga ticks
(#4), regenerated to a **markdown digest** (see Decided: operator view). Decomposition is
**draft-then-prune**, grown lazily, elaborated in place (#5). Each subplot is dispatched through **one
per-subplot seam** (#1) to the right executor — inline / fork / subagent / team / workflow / `/goal`
(#11) — chosen **by exception at the frontier under an attention budget** (#6), with the choice and its
**realized cost instrumented** (#10). Dispatch and completion ride **one bidirectional envelope** (#2):
a re-entry token out, an evidence tick back, parent-owned "done." **Concurrency** is made safe with
locks/idempotency/namespaced state (#9); outcome **state is portable** across machines/worktrees (#8);
**persistent session + worktree per sub-outcome** (#12). The board is a **secondary generated
portfolio** (#7). All of it ships together.

## Design components

### 1. One per-subplot dispatcher — generalize the by-mode fork off the downgrade path
Route each subplot to its backend through a single seam by promoting `recompile_for_tier()`'s by-mode
shape off the downgrade-only path, wiring the *existing* `team_emitter.py`, with a visible
HALT-not-degrade receipt when a backend can't actually run. The emitted artifact doubles as the
next-session handoff. Closes the silent team→inline correctness hole; a new backend becomes one branch.

| basis | `direct:` `execution_spec.py:708-724`, `team_emitter.py:71` (exists, tested), gaps 2/3; `operator-choice.md §6` | confidence 84 | complexity Med | axis A5 |
|---|---|---|---|---|

### 2. One bidirectional envelope — handoff token out, completion tick back, parent owns "done"
A subplot is a child saga; its handoff is a `/resume <subplot-saga-id>` re-entry token (not a
drift-prone pasted prompt) carrying a return channel; completion is a tick the child writes back via
`save()`, read by the parent via `read_ticks()`. "Done" is a **parent-owned barrier predicate over the
returned evidence**, not a child's self-report, and HALTs on an unmet contract. **Scope note (Codex):**
the recursion lives in *dispatch* (`orchestration_ref` → child spec), not in making `ExecutionSpec` the
outcome **state** store — outcome state is saga ticks + a thin subplot index.

| basis | `direct:` `saga.py` `save()`/`read_ticks()`/`restore()`, gaps 1/7/8; `external:` Step Functions task-token | confidence 82 | complexity Med | axis A4 |
|---|---|---|---|---|

### 3. Explicit `/outcome` cockpit, altitude-aware guts (was "no new command"; revised per Codex + R2)
The operator gets an **explicit** `/outcome report|next` surface — legible, not hidden behind
overloaded verbs — whose *internals* are "saga started higher," reusing the same engine and the
existing execution verbs (`/plan`/`/work`/`/loop`/`/resume`) under the hood. Explicit surface,
self-similar guts; no separate coordinate system. (The earlier "purely overload existing verbs"
position is retained as R2-inverse if the explicit surface proves redundant.)

| basis | `direct:` US5; Codex dissent ("no command hides altitude"); saga consumer map; `reasoned:` explicit cockpit + self-similar engine dissolves the binary | confidence 81 | complexity Med | axis A2 |
|---|---|---|---|---|

### 4. Operator as interrupt-handler over a pull-derived cockpit (empty surface = healthy)
The saga walks its own ready-frontier and auto-advances non-gated subplots; status is **derived on
read** (over `scan`/`read_ticks`/`dependency_layers`) with no operator-writable status field; it pages
the operator only at gates, unsatisfiable barriers, ambiguity, and parent-close. Re-entry replays the
decision trail ("why," not just "where"). Healthy steady state is an *empty* surface. **Depends on #9
(concurrency safety) before any auto-advance.**

| basis | `direct:` substrate survivors #3/#6, dead-wiring guard, flat `state.json`; `external:` K8s level-triggered controllers | confidence 78 | complexity Med–High | axis A2 |
|---|---|---|---|---|

### 5. Decomposition: draft → prune, grown lazily, elaborated in-place, row-promoted-to-saga
The saga drafts the subplot DAG (recursion via a subplot's `orchestration_ref` pointing at a child
spec — dispatch, not state store); the operator *prunes*; later layers grow lazily as evidence arrives;
an over-sized subplot elaborates in-place; a subplot is a cheap row until it *earns* promotion to its
own child saga. **These are four distinct mechanisms** (Codex flag) — draft/prune, lazy-grow,
elaborate-in-place, promote — each with its own edge cases (evidence/cost migration on elaborate; the
promotion trigger; parent/child ownership). Build deliberately, not as one undifferentiated blob.

| basis | `direct:` US3, substrate survivor #2, `execution_spec.py:337/347/361`; `reasoned:` subtraction is altitude-invariant, lazy matches info arrival | confidence 76 | complexity High | axis A1 |
|---|---|---|---|---|

### 6. Backend by exception under a frontier attention-budget; self-sharpening
Auto-bind the recommended backend for every non-gated subplot, prompt the operator only on gated ones;
decide at the ready-frontier under remaining attention/token budget (not per-node-in-isolation); every
override feeds `recommend_execution_backend()`'s R12 telemetry → `/optimize`. Never fold a gated subplot
into an advisory batch (governance split). Feeds and is fed by #10.

| basis | `direct:` `lifecycle_state.py:99`, R12 fields (`saga.py:174-175`), `override_rate_reader.py`; `external:` Airflow pools | confidence 79 | complexity Med | axis A3 |
|---|---|---|---|---|

### 7. Board as a secondary generated portfolio projection; subplot-namespace the validator state
The outcome's subplot-DAG progress auto-projects into mission-control as a generated **secondary**
portfolio view (no manual `/handoff`; gap 6); closing parents stays the operator's deliberate keystroke.
Namespace team-execution's validator state by subplot id (`.../<repo>/<subplot_id>/`, gap 4) so
concurrent same-repo subplots don't collide — that path doubles as the dispatcher's return address.

| basis | `direct:` gap 6 + substrate survivor #7, gap 4, "operator closes parents" | confidence 74 | complexity Med | axis A5 |
|---|---|---|---|---|

### 8. Portable / exportable outcome state (folded from Codex — MISSING)
Saga state lives under git-ignored `.claude/saga`; worktree cleanup, another host, or another session
lane can lose or fork it. An outcome that spans sessions/machines/worktrees needs an explicit
export/import (portable) state story so the DAG survives the operator's real multi-machine, multi-worktree
working pattern. (This is the known bg-worktree↔saga pain, one altitude up.)

| basis | `direct:` `.claude/saga` git-ignored location, `saga-spec §5.4`; Codex "cross-machine/worktree reality" | confidence 80 | complexity Med | axis A1/A2 |
|---|---|---|---|---|

### 9. Concurrency safety as a build invariant (folded from Codex — MISSING)
`state.json` is derived, last-writer-wins. Concurrent subplot execution needs explicit locks /
idempotency / duplicate-dispatch prevention + namespaced state (#7) — and #4's auto-advance and #6's
frontier dispatch **assume** this safety that doesn't exist yet. Model it as part of the build, not an
afterthought.

| basis | `direct:` flat `state.json` last-writer-wins (`saga-spec §5.4`), gap 4; Codex "concurrency safety" | confidence 81 | complexity Med–High | axis A5/A2 |
|---|---|---|---|---|

### 10. Economic instrumentation (folded from Codex — MISSING; the reason this exists)
Record per subplot: executor used, rough token/cost, wall-clock, operator touches, retries, accepted
evidence — and roll it up per outcome. The source problem was cost-vs-operator-time; without this, "a
DAG of right-sized executions saves cost" is an unfalsifiable vibe. This is what makes #6's lever and
the whole thesis measurable, and gives `/optimize`/`/retro` a portfolio-shaped consumer.

| basis | `direct:` source chat (cost origin), saga consumer map (`/optimize` off-chain), R12 telemetry; Codex "economic proof" | confidence 83 | complexity Med | axis A3 |
|---|---|---|---|---|

### 11. Forks + `/goal` in the executor menu (folded from Codex — RECONSIDER)
The per-subplot executor set must include **forks** (inherit + share the parent prompt cache — the cost
lever the source chat started from) and **`/goal`** (bounded autonomous loops), not just
inline/team/workflow. The recommender (#6) and dispatcher (#1) route to the full menu:
inline / fork / subagent / team-execution / cc-workflows-ultracode / `/goal`.

| basis | `direct:` source chat (forks share parent cache; `/goal` loops), US2; backend enum `saga.py:71` narrows to 3 today | confidence 78 | complexity Med | axis A3/A5 |
|---|---|---|---|---|

### 12. Persistent session + worktree per sub-outcome (folded from Codex — RECONSIDER)
A first-class operating rule: one durable session + worktree per **sub-outcome** (not per subtask), with
the outcome runner naming/owning it — the operating model the source chat recommended and the cache-cost
analysis endorsed. Couples to #8 (portable state) and #2 (re-entry token).

| basis | `direct:` source chat (persistent session/worktree per sub-outcome); Codex "reconsider" | confidence 77 | complexity Med | axis A2 |
|---|---|---|---|---|

### 13. Coordinator stays out of the execution loop; degrade only leaves (Antigravity)
The `OutcomeOrchestrator` never runs inside an execution context. Off-host / capability degradation steps a **leaf** down the ladder (`cc-workflows-ultracode` → `team-execution` → `inline`) per subplot — it **never** degrades the whole orchestration to `inline`, which would serialize the entire DAG into one agent context (token blowout, the agent loses the plot). The orchestrator manages the graph; only leaves execute.

| basis | `direct:` Antigravity #2, `recompile_for_tier` (`execution_spec.py:708-724`) | confidence 84 | complexity Med | axis A5 |
|---|---|---|---|---|

### 14. Completion sync from per-saga ticks, never the racy `state.json` (Antigravity)
The DAG-unlock signal — a subplot finished → release the next Kahn layer — reads **append-only per-saga completion ticks**, never the last-writer-wins `state.json` summary index (where B's `progress_pct` write silently clobbers A's completion → the orchestrator misses A finishing → the DAG **deadlocks permanently**). The `OutcomeOrchestrator` keeps its DAG/lock state in its **own** store, out of `state.json`. (Our #2's "completion = a per-saga tick" was already the right primitive; this names the rule: never the merged index.)

| basis | `direct:` Antigravity #3, `state.json` last-writer-wins (`saga-spec §5.4`), our #2 tick-back | confidence 85 | complexity Med–High | axis A5/A2 |
|---|---|---|---|---|

### 15. Failure-cascade semantics (Antigravity)
Define explicitly what happens to **in-flight siblings** when a subplot hard-blocks (missing credential, ambiguous requirement): pause the layer, cancel descendants, or let independent branches continue — a policy the coordinator enforces, not ad hoc per run. Without it, a blocked dependency leaves siblings burning tokens toward a result that can't land.

| basis | `direct:` Antigravity #4 | confidence 79 | complexity Med | axis A4 |
|---|---|---|---|---|

### 16. Attention consolidator (Antigravity)
The coordinator **aggregates concurrent leaf-blocks into a single operator prompt** — not five `blocked` subplots screaming from five tmux panes. One pane, one ranked "here's what needs you and why," bubbled up from the leaves. The cognitive-load telos made literal (and the consolidated form of #4's page-on-exception).

| basis | `direct:` Antigravity #4/#5, our #4 page-on-exception | confidence 81 | complexity Med | axis A2 |
|---|---|---|---|---|

## Decided: the operator view into the full saga

Both Claude and Codex (independently) converged: the **primary** view is a **derived on-read
`/outcome report`** — computed from parent saga + child saga ticks + execution refs + evidence + GitHub
pointers — **materialized to a regenerated markdown digest** at `docs/outcomes/<id>-report.md`,
overwritten from saga state on demand / on completion ticks. It is a readable artifact, never an
editable source of truth (so it physically can't drift). The **GitHub board is the secondary** portfolio
projection only (board-state vs saga-state stay distinct coordinate systems). A hand-maintained
`OUTCOME.md` log is rejected (dead-wiring drift). Form to be nailed in `/brainstorm`.

## Storage model — leaf-local ticks + a shared outcome store

The coordinator/executor split applies to storage too. Saga state today (`saga-spec.md §5.3`) is
**per-working-directory, git-ignored, volatile** — `<cwd>/.claude/saga/sagas/<saga_id>/`; the spec is
explicit that worktree saga state "lives only in that worktree's ignored `.claude/` and is discarded
on cleanup." So an outcome whose subplots run in **different worktrees / sessions** scatters its ticks
across isolated, throwaway dirs that neither the siblings nor the coordinator can see. That
per-worktree store **cannot** be the outcome's memory (the concrete form of #8 + #14).

**Two stores:**

| | Leaf saga (executor) | Outcome (coordinator) |
|---|---|---|
| holds | one thread's detailed ticks | the DAG · locks · subplot→saga pointers · append-only completion log · decision trail |
| where | stays `<worktree>/.claude/saga/` — bound to the worktree its branch/diff lives in | a **separate shared store** keyed by `outcome-id`, outside any worktree |
| lifetime | volatile; real output is the merged PR + a completion event published *up* | durable; survives worktree cleanup, session death, a multi-day gap |

When a leaf finishes it **appends a completion event** (done + PR ref + evidence pointer) to the
shared store; that **append-only** log is what the orchestrator reads to unlock the next Kahn layer —
append-only because the racy last-writer-wins `state.json` would eat completion events and deadlock the
DAG (#14). It is saga's own immutable-tick model, lifted to a shared home.

**Where the shared store lives, by reach:**
- **Same machine, many worktrees (the common case):** `$(git rev-parse --git-common-dir)/saga-outcomes/<outcome-id>/` — git worktrees share one `.git`, so this path resolves identically from every worktree and survives worktree cleanup. Zero new infra. (Or `~/.claude/saga/outcomes/`.)
- **Across machines:** promote the completion log to a networked store — **GitHub** (the objective + sub-issue tree is the durable, machine-independent DAG skeleton; PR-merged / issue-closed is completion; aligns with mission-control — it just can't hold `depends_on` edges, which live in the outcome spec) and/or **a networked Redis stream** (fast cross-host completion events).

**Decided shape** (the exact home is a `/brainstorm` detail): the orchestrator's working state lives at
the git-common-dir path as a **rebuildable cache**; the **durable source of truth is GitHub** (any
machine reconstructs the outcome from the sub-issue tree + PR/issue state); a networked Redis stream is
added only when subplots actually fan across hosts and sub-second completion matters. This mirrors
saga's existing philosophy — a durable canonical record + a rebuildable derived index — with GitHub as
the canonical record.

## Second opinion (Codex gpt-5.5, xhigh, read-only)

Independent read against both ideation docs, the source chat, and the saga/team-execution code.
Its reframe: *"saga-of-subplots is directionally right but too ontological — the better shape is an
outcome read-model / control plane over existing saga threads, with backends as executors. Don't make
recursive saga theory the product."*

- **Confirmed:** the dispatch/evidence spine (#1, #2, #6) and the operator-view answer (derived report +
  regenerated md digest + board secondary).
- **Dissented:** (a) don't make recursive `ExecutionSpec` the outcome **state** model — it's a unit
  emitter, fine for dispatch (→ scoped in #2/#5); (b) an explicit `/outcome` cockpit beats overloading
  verbs (→ #3 revised, R2 promoted); (c) decomposition is four bundled features (→ #5 flagged).
- **Surfaced (now folded as #8–#12):** cross-machine/worktree state portability; concurrency/locking
  safety before autonomy; economic instrumentation as the falsifiable proof; forks + `/goal` executors;
  persistent session/worktree per sub-outcome.
- **Emphasis:** Codex called the report + next-action + recommend-executor + emit-one-handoff loop the
  load-bearing core of operator value (woven through #1/#3/#4/#6 — noted as emphasis, not phasing).

## Second opinion (Antigravity Gemini 3.1 Pro, High, read-only)

Independent THIRD read, tasked with breaking what Claude and Codex agreed on. Verdict: **NO-GO on the architecture (outcome = saga), GO on the capability** — build an `OutcomeOrchestrator` that *owns* a DAG of sagas; keep sagas as strictly linear leaves.

- **Premise broken:** both prior passes accepted "outcome = self-similar saga"; `saga.py`'s linear `lifecycle_phase` cannot represent a concurrent DAG (the unanswerable: what is the outcome's phase mid-DAG?). A coordinator ≠ a leaf-executor; an outcome is an *Epic* (produces completed sagas; isn't itself code-reviewed/scanned).
- **Net-new failure modes (folded as #13–#16):** degrading the *orchestrator* to inline = context collapse; `state.json` as the sync primitive = permanent DAG deadlock (last-writer-wins eats completion events); no failure-cascade policy; no attention-consolidator (N blocked panes vs one prompt).
- **Reconciliation (adopted):** the coordinator/executor split costs nothing the operator wanted — *built into saga* + *reuse the machinery* both survive; only the "one dataclass for both" data-model self-similarity is dropped. See **Architecture reframe** (top).

## Did not survive (revivable)

| id | title | summary | reason | status |
|----|-------|---------|--------|--------|
| R1 | Self-grounding prose prompt (vs re-entry token) | The handoff is a generated self-contained prose prompt, not a `/resume` token. | #2 chose the token (no drift); revive for sessions that can't restore saga state. | rejected |
| R2 | Explicit `/outcome` command | A dedicated outcome cockpit vs overloading existing verbs. | **Revived** — Codex's UX argument promoted it into #3 (explicit surface, self-similar guts). | revived |
| R3 | Eager full up-front decomposition | Author the whole subplot DAG at plan time vs growing it lazily. | #5 chose lazy growth; revive for outcomes that need the full plan visible up front. | rejected |
| R4 | Decision-trail re-entry briefing as its own verb | A dedicated cold-start briefing that replays decisions, not just status. | Folded into #4; revive as a standalone `/resume`-scope briefing if the cockpit is too terse. | rejected |

## Co-ideation log

| source | entered | idea / seed | outcome |
|--------|---------|-------------|---------|
| user-seed | Phase 0 | US1–US6 (built-into-saga, per-subplot rec, saga-of-subplots, prompt-gen, surface, friend-executors) | survived as #1–#7 spine; US5 → #3 (explicit cockpit) |
| user-seed | Phase 6 | operator view into the full saga (board? md file?) | DECIDED above (derived report + regenerated md digest + board secondary) — Claude & Codex converged |
| frame-agent | Phase 2 | dispatcher / envelope / cockpit / decomposition / backend / portfolio | survived as #1–#7 |
| second-opinion | Codex gpt-5.5 | scope recursion to dispatch; explicit cockpit; portability; concurrency; measurement; forks+`/goal`; persistent session | folded as #2/#3 revisions + #8–#12 |
| second-opinion | Antigravity Gemini 3.1 Pro (High) | outcome ≠ self-similar saga (linear phase can't model a concurrent DAG) → distinct in-saga `OutcomeOrchestrator` over leaf sagas; degrade only leaves; ticks-not-`state.json` sync; failure cascades; attention consolidator | reframed the spine + folded as #13–#16 |
| user-question | storage | where does outcome state live across worktrees / sessions / machines? | **Storage model** section — two stores: leaf-local volatile ticks + a shared append-only outcome store (git-common-dir cache · GitHub canonical · optional networked Redis) |
