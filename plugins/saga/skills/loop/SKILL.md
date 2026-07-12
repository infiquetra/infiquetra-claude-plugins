---
name: loop
description: The Infiquetra lifecycle router and resume substrate. Three modes — Route (dispatch the one next command), Drive (walk phases across the lifecycle, pausing at every gate and handoff), and Resume (scan the saga, restore the work-thread, re-enter where it left off). Reads the saga at entry, ticks it on every routing decision, and routes to the destination command — which owns its own phase work, gates, AND its own execution backend. Triggers on "loop", "where does this go", "route this", "drive it through the lifecycle", "resume", "what's in flight", an issue/plan path, or a bare ad-hoc ask.
---

# Loop

`/loop` answers **"Where does this go, and what's already in flight?"** It is the lifecycle's
**router** and **resume substrate** — the front door that classifies an input, finds any in-flight
work, and dispatches to the one command that owns the next phase. It is **not** an execution engine:
it does not implement code, write plans, run reviews, or own a backend for the phase work it routes.
It routes, sequences (in Drive), and resumes — then the destination command does the work.

`/loop` is the campaign's **one native rebuild**: there is no upstream engine to port. CE has no
router; gstack has no dispatch SKILL; gstack's context save/restore is already the shipped saga
(`scripts/saga.py`) and is the queued `/resume`'s engine, not `/loop`'s. The dispatch table is
designed from the already-shipped infiquetra siblings' own clean-exit routing
(`references/dispatch-table.md`).

## Position in the lifecycle

`/loop` sits **above** every other command as the entry router and resume substrate. The other
commands answer one phase question each; `/loop` answers the meta-question of which one to run next:

- `/office-hours` answers: "What is even the right frame?"
- `/ideate` answers: "What are the strongest ideas worth exploring?"
- `/brainstorm` answers: "What exactly should one chosen idea mean?" (the WHAT)
- `/plan` answers: "How should it be built?" (the HOW)
- the `review` phase (`/doc-review`) answers: "Is this plan ready to execute?"
- `/work` answers: "Build it." (and owns the round-N PR loop to merge)
- `/code-review` answers: "Is the built code safe to merge?"
- `/qa` answers: "Does the shipped thing actually work?"
- **`/loop` answers: "Where does this go, and what's already in flight?"** (this engine)

`/loop` reads the saga to find in-flight work, picks the next command from the dispatch table, ticks
the saga with the routing decision, and dispatches. It is the substrate the other commands stand on,
not a competitor to any of them.

## Core principles

1. **Route and sequence; don't execute the phase work yourself.** `/loop` dispatches to the one next
   command and (in Drive) sequences across phases. The **destination command owns its phase work, its
   gates, AND its own backend** — `/loop` never re-implements `/work`, `/plan`, or a review, and never
   instructs a routed command's backend (`/work`'s Phase 1.4 offers its own; that is why `/loop` must
   not). The one exception is a `/loop`-OWNED router-level offload (Phase 3).
2. **The saga is the resume substrate.** `scan` at entry to find in-flight work; **tick every routing
   decision**; `restore` to re-enter a thread. `/loop`'s saga rows are the creation tick + a tick per
   routing decision; `status=handed-off` when routing to `/handoff` (saga-spec §11). Never set
   `next_round` — it is derived (saga-spec §6.1).
3. **Recommend the backend ONLY for what `/loop` itself drives.** Use
   `lifecycle_state.py recommend-backend` for `/loop`'s own Drive sequencing or a router-level sweep.
   Routed-to commands choose their own backend at their own offer; `/loop` never auto-hands a backend
   into them.
4. **Durable lives in the artifacts, not the cache.** The volatile saga points at committed `docs/*`
   plus issue/PR state. A cold resume reconstructs from those committed artifacts
   (`load_saga_context.py` + reading `docs/*`), never from the git-ignored cache as the authority. The
   saga in `.claude/saga/` is for offline match and the resume anchor; the committed
   docs and GitHub state are the source of truth.
5. **Own only the handoff envelope.** `/loop` owns routing + the handoff envelope
   (`handoff_envelope.py`). `mission-control` owns issues / boards / comments; `deploy` owns
   deploy mutation; the journal owns durable decisions. `/loop` points at those owners; it never
   reimplements them.
6. **Gate before routing, never block on a stub.** The one HARD gate routes to `/doc-review`
   (shipped) — block routing to `/work` on unresolved P0/P1 unless overridden with a recorded
   rationale. The route to shipped **`/qa`** is **advisory** (it is a gate-only node that produces a
   verdict but never blocks the router), and routes to **stub** targets (`/retro`, `/resume`, and
   `/strategy` / `/optimize` per their state) are **advisory** and **never** block `/loop` on their
   output.

## Interaction method

Use `AskUserQuestion` for choices from a known set (mode = Route / Drive / Resume, destination,
resume-vs-fresh, doc-review override, the `/resume` opt-in). Call `ToolSearch` with
`select:AskUserQuestion` first if its schema is not loaded. Ask one question per turn; prefer a concise
single-select when natural options exist. For open-ended discussion, ask inline in chat.

In a channel session (`redis-channel` active), `AskUserQuestion` cannot be called — inline the choices
in your reply text instead. Follow the canonical channel-inline convention in
`saga/skills/brainstorm/SKILL.md` (do not duplicate its wording here).

Gate-divergence telemetry (optional, issue #399): record the mode/destination choice via `gate_id`
`loop-mode-destination` per `plugins/saga/references/gate-divergence-instrumentation.md` when a
context-default mode or destination is offered.

Use repo-relative paths in every generated document and every routing tick. Absolute paths break
portability across machines and worktrees.

---

## Phase 0 — Enter, scan the saga, classify the mode

Capture the input and decide the shape of the run before routing anything.

### 0.1 Capture input

The input is a GitHub issue reference, a plan / requirements doc path, a bare ad-hoc ask, the word
`resume`, or `drive it`. Take it from command arguments or the active artifact. If empty, ask: "Where
should this go? Point me at the issue, a plan/doc path, describe the work, or say 'resume'."

### 0.2 Issue handoff routing

If the input is a GitHub issue, parse its body with `scripts/parse_issue.py` (it reads the body on
stdin and emits the `handoff` object). Use `handoff.maturity` for maturity routing:

- `idea-ready` / `requirements-ready` -> the next command is `/plan` (no plan exists yet).
- `plan-ready` / `resume-ready` -> the next command is `/work` (a plan already exists).

The parsed `flags` (`has_security`, `has_infra`, `has_api`) feed the hard test-gate check (Phase 2)
and the backend recommendation when `/loop` itself drives (Phase 3).

### 0.3 Scan the saga (find in-flight work)

Run `scan` at entry — this is the resume substrate's first move (saga-spec §11: `/loop` scans at
start to offer resume):

```bash
python3 plugins/saga/scripts/saga.py scan
```

`scan` returns one candidate per saga, newest-first by filename. Each candidate surfaces
`lifecycle_phase`, `phase_status`, `status`, `destination`, `issue_ref`, `plan_path`, and the
`orchestration` pointer (per the scan extension landing this same rebuild). Match a candidate to this
thread on `issue_ref`, `plan_path`, or operator confirmation. For an issue whose `issue-<N>` directory
is absent, resolve via `state.json.sagas[*].issue_ref` ending in `#N` — the id is sticky; **never**
rename the directory (slug-instability guard, saga-spec §2.3 / §2.1).

### 0.4 Classify the mode

- **Route** (default) — dispatch to the one next command for this input / phase. The command owns its
  phase + its own backend.
- **Drive** — the operator wants `/loop` to walk phases across the lifecycle (`drive it`). Sequence
  route -> dispatched-command-runs -> tick -> next, pausing at every hard gate and handoff (Phase 3).
- **Resume** — the input is `resume`, or Phase 0.3 surfaced an in-flight saga that matches. Restore
  and re-enter (Phase 1).

### 0.5 Render the idea->deploy arc (#344)

Whenever `/loop` presents state — at Route, Drive, and Resume entry — render the derived lifecycle arc
as the operator header via `project_arc` in `plugins/saga/scripts/status_card.py` (the same shared
card renderer `/work`, `/resume`, `/qa`, and `/code-review` use). It is a **pure projection of durable
saga fields** (`lifecycle_phase`, `phase_status`, `status`, `plan_path`, `review_paths`, `pr_refs`,
`destination`) — it reads no writable board Status column, board cache, or `board_progression`
write-record, so it renders what the saga asserts, never what the board says (KD4 derived-on-read).

**Boundary (#344 KTD3): `/loop` renders and sequences; it does not write the board.** `/loop`'s first
principle is route-and-sequence, not execute-phase-work — `mission-control` and the destination command
own board writes. The autonomous, allowlisted board progression (Status → Done, sub-issue close) fires
from **`/work`'s post-merge path** (which owns the merge), never from `/loop`. `/loop`'s board
contribution is the arc render plus sequencing the destination command that performs the allowlisted
write — the same end-to-end closure without `/loop` mutating the board itself.

---

## Phase 1 — Resume (lightweight restore + inline cold path)

### 1.1 Warm restore (the saga is present)

If Phase 0.3 surfaced an in-flight saga for this thread, restore it and re-enter at its saved phase:

```bash
python3 plugins/saga/scripts/saga.py restore --saga-id <issue-N|task-slug>
```

`restore` reads the latest tick (cold, branch-agnostic, no git / network). Re-enter at the restored
`lifecycle_phase` / `phase_status` and route from there (Phase 2). If `orchestration_ref` is set, this
thread is mid-flight inside a `/loop`-OWNED offload (a router-level Workflow `/loop` authored) —
**REPORT** the offload (its `orchestration_mode` + `orchestration_ref`) and let the operator decide,
rather than blindly re-dispatching it. Read `orchestration_ref` via `restore` (it is on the full
envelope), not via the `scan` candidate.

### 1.2 Inline cold reconstruction (the saga is cold or absent)

If the volatile saga is gone (a fresh machine / worktree, where the git-ignored
`.claude/saga/` was never copied), do a **minimal inline cold-reconstruction** from
the committed artifacts — the durable source of truth — rather than declaring the thread lost:

```bash
python3 plugins/saga/scripts/load_saga_context.py --repo <owner/repo> --issue <N>
```

That aggregates the restored saga (if any), round-tagged prior PRs, ADR refs, and matching journal
sections. Then read the committed `docs/*` (`docs/plans/`, `docs/work-sessions/`, `docs/brainstorms/`)
that the saga points at — those are durable; the cache is not. Route from the reconstructed phase.

### 1.3 Deeper forensics is opt-in, never auto

When cold reconstruction is not enough (tangled multi-round history, a corrupt local cache, a forensic
"what happened across these PRs" question), **OFFER** the `/resume` route as an **opt-in** — `/resume`
is the queued deep-reconstruction engine. **Never** auto-route into the `/resume` stub: `/loop` does
its own lightweight restore + inline cold path inline, and only suggests `/resume` when the operator
wants the heavy forensic dig. (`/resume` is a stub today; routing to it is advisory and never blocks
`/loop`.)

---

## Phase 2 — Destination decision + gates

Decide the destination class and apply the gates **before** picking the next command.

### 2.1 Normalize the destination

Normalize the routing intent to the canonical set with the helper, so the saga `--destination` stores
a clean enum:

```bash
python3 plugins/saga/scripts/lifecycle_state.py normalize <plan|pr|merge|deploy>
```

`normalize` maps user labels (`deploy` -> `nonprod-deploy`, etc.) to `plan-only | pr | merge |
nonprod-deploy`. The destination class is the routing horizon: `plan-only` stops at a written plan;
`pr` runs through `/work` to a PR; `merge` adds `/work`'s confirmed merge; `nonprod-deploy` hands
`deploy` after merge (`/loop` records the intent, never the deploy mutation).

### 2.2 The one HARD gate — doc-review readiness

Routing to `/work` from a plan is **blocked** when `/doc-review` reported unresolved **P0 or P1**
findings — unless the operator explicitly overrides **with a recorded rationale**. The target
`/doc-review` is shipped, so this gate has a real engine behind it. Do not treat chat memory alone as
durable evidence after a resume; read the latest matching artifact under `docs/reviews/` or the
same-session review output.

### 2.3 Other routing triggers

- **Hard test gate** — if the issue flags (`has_security` / `has_infra` / `has_api`) or the change
  kinds indicate `requires_hard_test_gate` work, the route to `/work` carries that as a constraint
  `/work` enforces (its Phase 3); `/loop` surfaces it, `/work` blocks on it.
- **Review triggers** — code at the work->PR boundary routes to `/code-review`; a plan / strategy with
  a scope / ambition question routes to `/founder-review`; a plan needing readiness review routes to
  `/doc-review`.

Pick the next command from `references/dispatch-table.md` using the input type, the saga's
`lifecycle_phase` + `phase_status`, and the handoff maturity.

---

## Phase 3 — Backend offer (for /loop-OWNED work) + optional Drive

### 3.1 Route (default) — no backend offer

In Route mode, `/loop` dispatches to the ONE next command and stops. That command owns its phase
**and its own backend** — `/loop` does **NOT** offer or instruct a backend for it. (`/work` runs its
own `recommend_execution_backend()` offer in Phase 1.4; `/plan` and `/code-review` run theirs.) This
is the across-vs-within boundary: **`/loop` drives ACROSS phases; `/work` drives WITHIN the work phase
(its round-N loop) — there is no competing driver.**

### 3.2 Drive — the agent-sequential cross-phase walk

In Drive mode, `/loop` walks the lifecycle: route -> the dispatched command runs and **owns its
within-phase execution** -> `/loop` ticks the saga -> pick the next command -> repeat. This is
honestly **agent-sequential**, not fire-and-forget: `/loop` pauses at **every hard gate** (the
doc-review P0/P1 gate) and **every handoff** for operator confirmation. See
`references/drive-and-resume.md`.

### 3.3 The backend offer is ONLY for a /loop-OWNED offload

For a **router-level broad fan-out** that `/loop` itself owns — e.g. a multi-issue sweep across many
threads, where `/loop` (not a single routed command) is the driver — `/loop` offers the execution
backend per `references/operator-choice.md` and may author a Workflow itself:

```bash
python3 plugins/saga/scripts/lifecycle_state.py recommend-backend \
  --broad-fanout --file-count <N> --phase-count <M>
```

Recommend the cheapest-correct backend, but render the offer from the full `backends` enumeration
(all three, each `{backend, status, note}`) so escalation is one step and no backend is silently
dropped, confirm with the operator, and record `--orchestration-mode` + `--orchestration-ref` in the
routing tick (Phase 4) **only in this `/loop`-owned-offload case** — never on an ordinary single-command
route. **Never omit `cc-workflows-ultracode` ("dynamic workflows") from the offer** — when the Workflow
tool is observably absent, still name it with `status: unavailable` and its availability-provenance note
(probed vs asserted); fall back to `/loop`'s own phase-walk when no heavier backend is reachable
(operator-choice §4).

---

## Phase 4 — Tick the saga + route

### 4.1 Write the routing tick

Emit a **runnable** routing-decision tick — the creation tick on first entry, then one tick per
routing decision (saga-spec §11). Carry `lifecycle_phase` forward to the destination phase; **never
clobber** a consumer's `lifecycle_phase` — pass the phase the destination owns, mirroring
`/code-review`'s preserve discipline. Never `git add` the tick (saga state is git-ignored,
machine-local):

```bash
python3 plugins/saga/scripts/saga.py save \
  --kind <issue|task> \
  --id <issue-number-or-task-slug> \
  --lifecycle-phase <target-phase> \
  --phase-status <pending|in_progress|complete> \
  --destination <plan-only|pr|merge|nonprod-deploy> \
  --next-step "<the one imperative resume anchor: the command being routed to>" \
  --issue-ref <owner/repo#N> \
  --plan-path docs/plans/YYYY-MM-DD-<topic>-plan.md \
  --rounds-seen "<observed round numbers>"
```

`--id` is the only strictly required flag (`--kind` defaults to `issue`); for ad-hoc work pass
`--kind task --id <slug>`. Never set `next_round` — it is derived from `rounds_seen` (saga-spec §6.1).
Add `--orchestration-mode <...> --orchestration-ref <...>` **ONLY for a `/loop`-owned offload**
(Phase 3.3), **not** on an ordinary route.

### 4.2 Routing to /handoff

When routing to `/handoff`, set `--status handed-off` on the tick and build the handoff envelope:

```bash
python3 plugins/saga/scripts/handoff_envelope.py --source <docs/...path> --reason "<why>"
```

The envelope's `suggested_command` (`/issue --prepare --from <source> --maturity <maturity>`)
is what `/handoff` carries into `mission-control`. `/loop` builds the envelope; `mission-control` owns the
issue artifact.

### 4.3 Dispatch

Announce the chosen next command with a one-line reason, then dispatch. In Route mode, stop after the
dispatch. In Drive mode, return here after the dispatched command completes a phase, tick again, and
route to the next command (pausing at every hard gate and handoff).

### 4.4 Hard boundary

`/loop` routes, sequences, resumes, and owns the handoff envelope. It does **NOT**: implement code
(-> `/work`), write a plan (-> `/plan`), run a review (-> `/doc-review` / `/code-review` /
`/founder-review`), run QA (-> `/qa`), file SDLC issues (-> `mission-control`), deploy
(-> `deploy`), instruct a routed command's backend (each owns its own), or do heavy
forensic reconstruction (opt-in -> `/resume`). Route, tick the saga, dispatch — then stop (Route) or
continue the walk (Drive).

---

## Reference files

- `references/dispatch-table.md` — the designed dispatch map, total over all 15 routable commands:
  the cold-start entry, the main chain, the off-chain commands, the routing gates, the
  destination-class meaning, and the stub-target advisory rule.
- `references/drive-and-resume.md` — the Drive cross-phase walk (agent-sequential, pause-at-gates, the
  across-vs-within boundary with `/work`, when `/loop` authors a Workflow) and the Resume contract
  (scan -> restore -> route, the routing-tick shape, the volatile-vs-committed durability split, the
  inline cold reconstruction, and the opt-in `/resume` advisory).
