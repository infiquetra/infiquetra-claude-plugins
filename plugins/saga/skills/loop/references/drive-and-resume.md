# Drive and Resume

The two `/loop` modes beyond plain Route. **Drive** sequences across phases; **Resume** restores an
in-flight thread. Both are router behaviors: neither executes a phase's work itself — they sequence and
re-enter, and the destination command does the work.

---

## (a) Drive — the agent-sequential cross-phase walk

### What Drive is

Drive walks the lifecycle one phase at a time:

```
route ─► dispatched command runs (owns its within-phase execution) ─► /loop ticks the saga ─► next ─► …
```

`/loop` picks the next command (`dispatch-table.md`), dispatches it, lets it own its phase work and
its own backend, then ticks the saga with the routing decision and picks the following command. It
repeats until the destination class horizon is reached (`plan-only` / `pr` / `merge` /
`nonprod-deploy`) or a pause point is hit.

### It is agent-sequential, NOT fire-and-forget

Be honest about this: Drive is a sequential agent walk, not autonomous unattended execution. `/loop`
**pauses for operator confirmation** at:

- **every hard gate** — the doc-review P0/P1 readiness gate (the only hard routing gate);
- **every handoff** — routing to `/handoff` / `mission-control`, or a deploy hand to `deploy`;
- **any destructive or outward mutation** the dispatched command would surface (e.g. `/work`'s
  merge confirmation — `/work` owns that, not `/loop`).

Between pauses, `/loop` advances on its own; at a pause, it stops and asks.

### The across-vs-within boundary with /work

State this boundary explicitly: **`/loop` drives ACROSS phases; `/work` drives WITHIN the work phase
(its own round-N PR continuation loop).** When Drive routes into `/work`, `/loop` hands off the entire
work phase — `/work` owns the round-N loop, the test gates, the code-review call, and the merge
confirmation. `/loop` does not interleave with `/work`'s internal loop; it waits for `/work` to
complete its phase, then ticks and routes onward. There is **no competing driver** inside a phase.

### When /loop authors a Workflow (router-level sweep ONLY)

`/loop` offers an execution backend and may author a Workflow **only** for a `/loop`-OWNED
router-level offload — a broad fan-out where `/loop` itself is the driver, not a single routed command.
The canonical case is a **multi-issue sweep** (the same routing operation applied across many threads).
In that case:

```bash
python3 plugins/saga/scripts/lifecycle_state.py recommend-backend \
  --broad-fanout --file-count <N> --phase-count <M>
```

Recommend the cheapest-correct Saga backend (`inline` or `team-execution`). The full wire enumeration
still carries all three backends (`{backend, status, note}`), with `cc-workflows-ultracode` as an
alternative (or unavailable when the Workflow tool is absent), never a silent drop. Confirm, and record
`--orchestration-mode` + `--orchestration-ref` in the routing tick — this pair appears **only** in the
`/loop`-owned-offload context, never on an ordinary single-command route. An ordinary route hands the
backend choice entirely to the destination command (which makes its own offer); `/loop` does not
instruct it.

### The inline phase-walk is the cross-host fallback

When no heavier backend is reachable (the Workflow tool is absent — e.g. a redis-channel session or
another runner), Drive degrades cleanly to `/loop`'s own **inline agent-sequential phase-walk**. This
is the same attempt-then-degrade pattern operator-choice §4 names: try the rich path, fall back to
inline with a one-line note. The phase-walk always works on any host.

---

## (b) Resume — scan -> restore -> route

### The contract

Resume is the saga round trip:

1. **`scan`** at entry — `saga.py scan` lists one candidate per saga, newest-first, surfacing
   `lifecycle_phase` / `phase_status` / `status` / `destination` / `issue_ref` / `plan_path` /
   orchestration pointer. Match on `issue_ref`, `plan_path`, or operator confirmation.
2. **`restore`** the matched thread — `saga.py restore --saga-id <id>` reads the latest tick cold
   (branch-agnostic, no git / network). The full envelope (including `orchestration_ref`) is here, not
   in the scan candidate.
3. **route** from the restored `lifecycle_phase` / `phase_status` via `dispatch-table.md`.

### The routing-tick `save` shape

Every routing decision writes a tick (creation tick on first entry, then one per decision):

```bash
python3 plugins/saga/scripts/saga.py save \
  --kind <issue|task> --id <...> \
  --lifecycle-phase <target-phase> --phase-status <pending|in_progress|complete> \
  --destination <plan-only|pr|merge|nonprod-deploy> \
  --next-step "<the command being routed to>" \
  --issue-ref <owner/repo#N> --plan-path docs/plans/<file>.md \
  --rounds-seen "<observed rounds>"
```

Carry `lifecycle_phase` forward (the destination's phase) — never clobber a consumer's phase. Never set
`next_round` (derived, saga-spec §6.1). Add `--status handed-off` when routing to `/handoff`. Add
`--orchestration-mode` / `--orchestration-ref` only for a `/loop`-owned offload.

### Durability split — volatile cache vs committed artifacts

| Tier | Location | Role |
|---|---|---|
| Volatile cache | `.claude/saga/` (git-ignored) | the saga ticks + `state.json` index — offline match + resume anchor. **Not** authoritative; never copied across worktrees. |
| Durable artifacts | committed `docs/*` (`docs/plans/`, `docs/work-sessions/`, `docs/brainstorms/`, `docs/reviews/`) + GitHub issue / PR state | the **source of truth**. A cold resume reconstructs from these. |

The cache points; the committed docs are the truth. A resume that finds a stale or absent cache falls
back to the durable artifacts — it does not declare the thread lost.

### Inline cold reconstruction (cache gone)

On a fresh machine / worktree where `.claude/saga/` was never copied, reconstruct
inline from the durable side:

```bash
python3 plugins/saga/scripts/load_saga_context.py --repo <owner/repo> --issue <N>
```

That aggregates the restored saga (if any), round-tagged prior PRs (via `gh`, no-raise if missing),
ADR refs, and matching journal sections. Then read the committed `docs/*` the context points at. Route
from the reconstructed phase. This is `/loop`'s **own** lightweight cold path — done inline, not
delegated.

### Resuming into a mid-flight /loop-owned offload

If the restored saga has `orchestration_ref` set, the thread is mid-flight inside a Workflow `/loop`
authored (a router-level offload). **REPORT** it — name the `orchestration_mode` + `orchestration_ref`
and let the operator decide — rather than blindly re-dispatching. Read `orchestration_ref` via
`restore` (the full envelope), not via the `scan` candidate (which carries only the orchestration
pointer summary).

### Deep forensics is opt-in — never auto-route into /resume

`/loop` does lightweight restore + the inline cold path itself. For heavy forensic reconstruction
(tangled multi-round history, corrupt cache, "what happened across these PRs"), **OFFER** the
**opt-in** `/resume` route — `/resume` is the queued deep-reconstruction engine. **Never** auto-route
into `/resume` and **never** block `/loop` on it; routing to `/resume` is advisory and
operator-confirmed.
