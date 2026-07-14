---
name: outcome
description: Coordinate a whole outcome as a durable DAG of leaf sagas. A level-triggered reconcile loop that dispatches the ready frontier to executors, harvests completion, and pages the operator only at gates and exceptions. The coordinator routes and never runs leaf work; status is derived on read. Thin coordinator verbs only — start, graph, advance, attend, resume, export, import — leaf work stays the native /resume, /work, /code-review, /qa.
---

# Outcome

`/outcome` is the **OutcomeOrchestrator**: the layer above a single work-thread saga that drives a whole
*outcome* — outcome → subplots (leaf sagas) — as a concurrent, durable DAG across sessions, worktrees,
and machines. The human is an interrupt-handler on gates and exceptions; the runner advances everything
else.

This skill is the thin operator surface over the reconcile engine
(`plugins/saga/scripts/outcome.py`), the spec (`outcome_spec.py`, U1 — structure) and the store
(`outcome_store.py`, U2 — the git-common-dir cache, completion events, locks, replay ledger).

## Position in the lifecycle

`/outcome` sits **above** the saga lifecycle, not inside it. A leaf subplot is a normal linear saga that
runs the usual `/plan → /work → /code-review → /qa` on its own branch/worktree. `/outcome` coordinates
*which* leaves are ready, dispatches them, and harvests their completion — it never replaces the leaf
verbs. The altitude seam is explicit: `attend` hands you the native `/resume <leaf-saga-id>` to drop into
a leaf hands-on, then you come back up to `/outcome`.

## Core principles

1. **The coordinator routes, it never executes (R2/R3).** `advance` dispatches ready leaves to their
   backends and reads their completion events. It must never run a leaf's work in the advance process —
   doing so would collapse the whole DAG into one inline context and lose the plot. There is no
   `/outcome work`.
2. **Level-triggered, not imperative (R29).** Every tick reconstructs from the durable store, advances
   the ready frontier, and sleeps. It holds no authoritative in-memory DAG, so a crash mid-run is
   recoverable — the next tick re-derives. `/goal` and compiled workflows are *executors it dispatches
   to*, never the host.
3. **Status is derived on read (R17).** No operator-writable status field. A node's live state is
   computed each call from the committed spec + completion events + dispatch records. A healthy steady
   state is an empty surface — you are paged only at gates, unsatisfiable barriers, ambiguity, and
   parent-close.
4. **The committed spec is canonical for structure; GitHub for completion; the cache holds nothing
   canonical (R26/R27).** Deleting the git-common-dir cache loses nothing — `resume` rebuilds it.

## The thin surface (KTD11)

Coordinator-only verbs — run via `python3 plugins/saga/scripts/outcome.py <verb> ...`:

| verb | does |
|---|---|
| `start <id> <objective> [--intent-file <envelope.json>]` | create the branch-local spec (`docs/outcomes/<id>/outcome-spec.json`) + its store; commits the run-start intent envelope when one is supplied or issue-carried (#380 — see "Run-start intent envelope") |
| `graph <id>` | print a Mermaid DAG annotated with each node's derived live state (one-glance topology) |
| `advance <id> [--loop]` | one (or repeated) reconcile ticks — dispatch the ready frontier, idempotently |
| `attend <id> <subplot>` | print the native `/resume <leaf-saga-id>` handoff for a leaf you want hands-on |
| `resume <id>` | reconstruct live status from spec + store (works even if the cache was wiped) |
| `status <id>` | the derived-on-read cockpit snapshot — rendered as the operator status header via `project_outcome` in `plugins/saga/scripts/status_card.py` (states, counts, frontier, milestone health) |
| `commit <id> [--push]` | **commit (+ push) the spec to the outcome's own branch** — the R26/R27 cross-machine durability step (refuses on `main`/`master`) |
| `report <id>` / `project <id>` | regenerate the derived-on-read status card via `project_outcome` (R19/R25); when a completion event carries a `manifest_ref` pointer, resolve it via `manifest_store.resolve_manifest_ref` to show the leaf's producer attribution and disposition (advisory, R8) — the single emitter of the operator-facing outcome summary; the card's cells (milestone health, leaf progress, frontier, blockers) are derived on read from the committed spec + completion events, never from an operator-writable status field |
| `approve <id>` / `prune <id> <subplot>` / `promote <id> <subplot> <child>` | the R20 frontier approval + the R33 graph edits |
| `repost <id> [--scope <subplot>] --set FIELD=VALUE --reason <why>` | renegotiate a LIVE campaign's posture mid-run (#433) — atomic snapshot→validate→bump→trail; merge/deploy gates are monotonic (auto→gate only, enforced identically on a live `set-intent` attach); a loosening repost re-closes the frontier approval; in-flight leaves finish under dispatch-time posture, dispatch AND completion gates both, and a mid-tick repost survives a concurrent advance (stale-save guard + tick reload) (see `references/outcome-spec.md` §Mid-run posture renegotiation) |
| `reconcile <id> [--resolve <drift-id> --action ...]` | detect board↔saga drift over the board-sync ledger (#295); silent unless divergent, `--resolve` applies an operator decision (see Reconcile-on-wake) |
| `export <id>` / `import <bundle>` | a portable spec + completion bundle to move an outcome across machines |

**Persist the spec to the branch (R26/R27).** The committed `docs/outcomes/<id>/outcome-spec.json` on the
outcome's own branch (`outcome/<slug>`, never `main` mid-run) is what lets a **different machine
reconstruct the whole outcome by pulling the repo** — load the committed spec, then re-harvest completion
from GitHub (canonical), with no dependence on the local cache. `start` and the graph edits write the
working-tree file; **commit + push is explicit**: run `/outcome commit <id> --push` after structural
changes, or `/outcome advance <id> --persist` to commit the (cost-rollup-updated) spec each tick on an
unattended `/loop` run. The *cadence* is yours; the *mechanism* is `commit`/`--persist`. (`export`/`import`
remain the cache-derived bundle for an ad-hoc move; the committed-branch path is the canonical durability.)

Leaf work is **always** the native verbs on the leaf's own saga: `/resume <leaf-saga-id>`, `/work`,
`/code-review`, `/qa`. Never shadow them.

## Run-start intent envelope (#380)

Run-start posture is captured **once**, as one committed envelope on the spec (`intent`:
run_mode + ceremony_gates), through the fleet's single interview registry
(`plugins/saga/scripts/intent_envelope.py`; full contract in
`plugins/saga/references/intent-envelope.md`). Never ask your own posture question — the fleet
drift-guard test fails the build on any posture question defined outside the registry.

At `start`:

1. `start --from-objective <owner>/<repo>#<N>` reads the parent Objective's body. A **valid**
   issue-carried envelope (the `### Intent envelope` fenced block mission-control authors at
   capture) is committed onto the spec and the interview is **skipped** — the operator already
   answered once, on the issue. The start output reports
   `{"intent_source": "issue", "interview_required": false}`.
2. When the output says `interview_required: true` (no envelope, or an invalid one — the reason
   is surfaced, an invalid envelope is never adopted): the spec already exists (`start` is
   non-idempotent — never re-run it), so render the single interview with data-backed stakes,
   capture the operator's typed answers, and commit the envelope onto the started outcome with
   `set-intent`:

   ```bash
   python3 plugins/saga/scripts/intent_envelope.py interview --outcome-spec <spec.json>
   # present the manifest (AskUserQuestion, or inline in a channel session), then:
   echo '<answers JSON {qid: option}>' | python3 plugins/saga/scripts/intent_envelope.py capture - > envelope.json
   python3 plugins/saga/scripts/outcome.py set-intent <id> --intent-file envelope.json
   ```

   `set-intent` validates exactly like `start --intent-file` (an invalid file is a loud error),
   refuses to overwrite a committed envelope (mid-run renegotiation is the `repost` verb, #433),
   and bumps `spec_revision` through the one revision counter with a `set-intent` decision-trail
   entry — re-`approve` before the next dispatch. Once the campaign is LIVE (any dispatch
   record), a first attach passes the SAME monotonic merge/deploy validation as a repost: an
   envelope carrying `merge`/`deploy_nonprod: "auto"` is rejected outright (#433 AC5 — no
   second-verb side door); before any dispatch, any posture attaches (the interview-fallback
   contract above). To CHANGE posture on a live campaign — run mode, ceremony gates, a leaf's
   degrade policy or sandbox — use `repost` (one atomic verb; merge/deploy gates only ever
   tighten; a `degrade_policy`-borne guarantee HALT offers a scoped `repost --scope <subplot>`
   resolution instead of a dead stop — other halt classes page the operator without the offer,
   because no repost value can resolve them).

3. On a genuinely unattended start with no operator to interview, the run self-selects its
   posture from the mode default matrix (`self_select_posture` — every ceremony gate stays
   `gate`), never by inventing answers.

Downstream, the committed envelope is machinery, not prose: `ceremony_gates.reviews_required:
"gate"` gates every code leaf's `done` transition on recorded `code-review` evidence at the
close SHA (via the closure gate) — a merged-but-unreviewed leaf stays undone until the evidence
lands. `ceremony_gates.merge` is consumed by the auto-merge queue (#449): every merge-class
GitHub write (rebase, squash) requires the committed `merge: "auto"` posture AND one active
envelope token (`envelope_token.py mint/revoke/check` against the outcome store; see
`references/envelope-token.md`), re-checked fresh per attempt — an envelope-less campaign, a
`gate` posture, or a token-less `auto` posture all wait for the operator's keystroke, and
every authorized merge is attributed to its `authorizing_envelope_id` in the board-sync
ledger. `deploy_nonprod` still records posture only; it does NOT create an autonomous write
path (deploy is out of #449's scope — the certificate's deploy GATE stands).

The envelope's optional **dispatch-seam posture** (#373 — `backends_permitted`,
`degrade_policy`, `spend_envelope`) is enforced inside every `advance` tick: the effective
backend menu is captured ∩ runtime (`--host-capable`/`--workflow-available` stay the runtime
half), an unmet backend HALTs by default and degrades **at most one rung** only under a
captured `operator_away_one_rung`, and the spend envelope is a HALT-only pre-dispatch gate
against the leaf-produced cost actuals — an over-ceiling or tier-escalating leaf surfaces a
`spend-halt` receipt in `result.halted` and waits for explicit step-up (mid-run renegotiation
is #433's contract). Full semantics: `plugins/saga/references/intent-envelope.md`.

## How a reconcile tick works (`advance`)

1. Load the canonical spec (branch) and open the store (git-common-dir cache).
2. Acquire the **coordinator lease** — a second concurrent `advance` no-ops on a held lease and reclaims
   a stale one (R13), so two ticks (a cron tick overlapping a manual one) never both mutate.
3. Recompute `completed` from the store's completion events and the **ready frontier** from the spec
   (`ready_frontier`, the level-triggered read).
4. For each ready, not-yet-dispatched, not-completed leaf: take its per-subplot dispatch lock and
   **dispatch** it to its backend (record the handoff in the ledger). Already-dispatched leaves are
   skipped — repeated ticks never double-dispatch (idempotent).
5. Return the derived status. Pages only on exceptions.

The execution backends a leaf can be dispatched to — inline / fork / subagent / team-execution /
cc-workflows-ultracode / `/goal` / manual — are wired in later units; the dispatch *seam* and the
reconcile loop are the contract.

## Autonomous board-sync (`advance --autonomous`)

By default `advance` performs **no** GitHub writes — it dispatches and derives status, nothing more. The
opt-in `--autonomous` flag lets a tick *also* move the operations board to match each leaf's derived state,
but only inside a strictly **enumerated, reversibility-gated envelope**. Every candidate write is checked
against the reversibility certificate (`reversibility_certificate.authorize_write`), which **defaults to
GATE**: a write happens only when the op is one of the enumerated, reversible-or-additive kinds.

**Performed autonomously when authorized:**

- **Set the leaf's Status field** to `In Progress` when the leaf enters its ready/dispatched frontier
  (reversible: the inverse is setting the prior value).
- **Close the leaf's sub-issue** when the leaf reaches its done state (reversible: the inverse is reopen).
- **Add or remove an issue label** (each is the other's inverse).
- **Post one coalesced progress comment** per meaningful leaf transition — additive, append-only, and
  bounded by a coalescing idempotency key so rapid repeat ticks never spam duplicate comments.

**Never autonomous by default — the operator's keystroke, with ONE scoped, revocable exception (#449):**

- **Deploying** — irreversible side effect, permanently human-in-the-loop (no exception exists;
  deploy is explicitly out of #449's scope).
- **Merging a PR** — GATE by default, everywhere, for every campaign that has not explicitly
  opted in. The single exception is #449's `AUTONOMOUS_UNDER_ENVELOPE` write class (the intake
  §3 revisit condition, engaged deliberately — the default did not flip): the merge queue may
  squash autonomously ONLY when the campaign's committed envelope declares
  `ceremony_gates.merge: "auto"` AND exactly one active (unexpired, unrevoked,
  era-bound) merge-scope envelope token resolves from the outcome store — re-checked fresh
  before every rebase/squash, so `envelope_token.py revoke` stops the very next write with no
  grace window. Every authorized merge is attributed to its `authorizing_envelope_id` in the
  board-sync ledger, both pre-squash and post-squash. No envelope, a `gate` posture, a
  token-less `auto` posture, an expired/revoked token, or an ambiguous token lane → the leaf
  `waits-operator` with the precise reason. Bare `merge` stays absent from the certificate
  allowlist — `authorize_write` still GATEs it for every caller.
- **Closing the parent issue** — `parent-issue-close` is classified `ALWAYS_OPERATOR`, so it GATEs even
  though a close is mechanically reversible: declaring the whole outcome done stays a deliberate decision.

**Everything else GATEs to the operator.** Any op not in the enumerated allowlist (an unrecognized verb, a
repo mutation, anything the certificate does not recognize) is **denied by default** and surfaced — there
is no silent write and no silent skip. A GATE produces a visible `gated` record, not a no-op.

**Idempotent, fail-loud, and recorded.** Each authorized write carries a deterministic idempotency key
recorded in a **separate board-sync ledger** (never the completion event log), so a crash or a repeated
tick re-runs as a no-op rather than a duplicate. A write that fails is **retried under the same key** a
bounded number of times and then **surfaced as a failed record** — the campaign is never silently wedged
and never silently skips the write. **Every autonomous write is recorded** (in the tick's
`board_synced` results) so there is an auditable trail of what the coordinator changed, when, and why it
was authorized.

## Reconcile-on-wake (`reconcile`, and `advance --autonomous`)

Autonomous board-sync writes the board but never re-reads it, so an **outside** writer — the operator, a
CI bot, a review agent — who changes a saga-owned field while saga is at rest goes unnoticed, and because
a recorded idempotency key makes the next tick *skip* the op, that drift would persist silently. **Reconcile
closes that loop** (#295): it re-fetches the saga-owned fields, diffs them against what the ledger recorded,
and surfaces any divergence for you to resolve. It adds no writer of its own and no new persistence.

**When it runs.** Automatically at the top of every `advance --autonomous` tick, *before* any board write
(a detected drift **drift-holds** only that issue's ops for the tick — `{status: drift-hold}` — while other
leaves proceed), and on demand via `outcome reconcile <id>` (read-only; no coordinator lease). It is silent
unless something diverged.

**The saga-owned field class** is exactly what the writer writes: board **Status** and issue **open/closed**.
A field saga never wrote (a hand-added label) is out of scope and never a false positive. An external close
is **contract-aware**: a `completed` close that satisfies a non-code leaf's completion contract is the
harvester's sanctioned path and stays silent; a `not_planned` close, or a close on a code leaf (whose
contract is a merged PR, not a closed issue), is drift.

**Resolving a drift.** Each divergence surfaces as one line — `{kind} {repo}#{number}: saga={X} board={Y}
(author?)` — and offers three actions (`outcome reconcile <id> --resolve <drift-id> --action ...`):

- **accept-board** — the board's value wins; recorded as an append-only override so it never re-flags. For a
  `not_planned` external close this records the acceptance but mints **no** completion event — it advises
  `/outcome prune <subplot>` to drop the leaf from the frontier (a graph edit stays yours).
- **re-assert** — saga's value wins; re-driven through the certificate (`authorize_write` first) and the
  same board-sync writer, never a direct write.
- **hold** — records nothing; the drift resurfaces on the next detection.

Resolution is **human-in-the-loop** today, behind a single replaceable policy seam so a future
writer-precedence rule ("field X's authoritative writer auto-resolves") can supersede the ask without
touching detection. Use `AskUserQuestion` (or, in a channel session, inline the three choices) — one line
per drift.

## Interaction method

Drive `/outcome` for coordination; drop to native leaf verbs for hands-on work. When several leaves block
at once, the attention consolidator (later unit) bubbles them into one ranked prompt rather than N pages.
Use `AskUserQuestion` only for genuine coordinator-level decisions (a gate, an unsatisfiable barrier, a
parent-close); in a channel session, inline the choices instead. Gate-divergence telemetry (optional,
issue #399): record such a decision via `gate_id` `outcome-coordinator-decision` per
`plugins/saga/references/gate-divergence-instrumentation.md` when a recommended resolution is offered.

## What `/outcome` does NOT own

- Authoring the graph from scratch — that is `/plan` + the decompose flow (a later unit).
- Running any leaf's implementation — that is the leaf's native saga.
- Filing SDLC issues (`mission-control`) or deploying (`deploy`).
- A stored status field — status is always derived.

Arguments provided to the command:

`$ARGUMENTS`
