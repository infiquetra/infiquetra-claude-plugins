---
name: resume
description: The Infiquetra lifecycle's HEAVY forensic reconstruction engine — the deep half beside /loop's lightweight restore. Two tiers — Tier 1 reconstructs from the saga's WHOLE tick-chain trajectory (not just the last frame) plus PR archaeology and explicit conflict reconciliation; Tier 2 (fallback only, no saga AND no resolvable issue) is a slim Claude-only port of CE session forensics over local JSONL logs. Read-only on the world; it writes one git-ignored re-entry tick that reuses the restored saga_id, then routes. Triggers on "resume", "reconstruct what happened", "what was tried across these PRs", a corrupt or missing local cache, or same-machine work that never wrote a saga.
---

# Resume

`/resume` answers **"What actually happened here, across the whole history — and where do I re-enter?"**
It is the lifecycle's **heavy forensic reconstruction engine**: the deep dig that runs when a thread is
tangled across many rounds and PRs, when the local cache is corrupt or absent, or when same-machine work
ran before any saga was ever written. It reconstructs the full trajectory, reconciles conflicts against
the durable source of truth, and then **routes** to the one command that owns the next phase. It does
**not** build, plan, review, file issues, or deploy — it reconstructs and hands off.

`/resume` is the **deep half beside `/loop`**. `/loop` already does the lightweight restore (latest tick)
and the inline cold reconstruction (`load_saga_context.py` + reading `docs/*`) — see
`../loop/references/drive-and-resume.md` (the Resume contract). `/loop` **offers** `/resume` as an
opt-in only when the lightweight path is not enough. `/resume` is what it offers: the all-ticks
trajectory read, deeper PR archaeology, conflict reconciliation, and — as a last resort — JSONL session
forensics. It never routes back to `/loop` (no ping-pong); it routes forward to the owning command.

## Position in the lifecycle

`/resume` sits beside `/loop` as the resume substrate's **forensic** tier:

- `/loop` answers: "Where does this go, and what's already in flight?" (lightweight scan / restore / route)
- **`/resume` answers: "What happened across the whole history, and where do I re-enter?"** (this engine)
- the destination command (`/work`, `/handoff`, …) answers its own phase question once routed to

`/loop` does the cheap restore inline; `/resume` is the expensive dig `/loop` defers to. The two
reconcile **identically** — they inherit the same durability precedence (committed `docs/*` + GitHub
authoritative; the git-ignored saga cache is the anchor, not the authority). The only difference is
depth: `/resume` reads the whole tick chain, not the last frame.

## Core principles

1. **Reconstruct from the durable source of truth.** Committed `docs/*` and GitHub issue / PR state are
   authoritative; the git-ignored saga cache in `.claude/infiquetra-lifecycle/` is the **anchor, not the
   authority**. This is the **existing** precedence — `../loop/references/drive-and-resume.md` lines
   108-111 and `../../references/saga-spec.md` §10 — **inherited, not reinvented**, so `/loop` and
   `/resume` reconcile a stale cache against a merged PR the same way.
2. **Read the WHOLE trajectory, not the last frame.** Tier 1 reads **all** saga ticks oldest -> newest
   (the new `ticks` reader) and reconciles them via the §6 full-snapshot semantics — answered questions
   dropped off, cleared blockers vanished, phase regressions surfaced. This all-ticks read **plus**
   deeper PR archaeology **plus** explicit conflict reconciliation is what makes `/resume` deeper than
   `/loop`. `load_saga_context.py` and reading `docs/*` are **shared substrate** `/loop` already runs —
   they are **not** the differentiator. (See `references/forensic-reconstruction.md`.)
3. **Reconcile conflicts explicitly, operator-confirmed.** When the cache disagrees with reality — a
   stale `lifecycle_phase` vs a merged PR, an open blocker the PR already cleared — surface the conflict,
   apply the precedence (committed + GitHub win), and confirm the reconciled state with the operator
   before routing. Never silently trust the cache.
4. **Zero-save JSONL forensics is the last resort, context-safe by construction.** Tier 2 fires **only**
   when there is no saga AND no resolvable issue. The **orchestrator NEVER Reads or cats a raw `.jsonl`
   or a skeleton file.** Discovery returns paths; extraction is **file-mediated** to a scratch dir; a
   **GENERIC synthesis agent** (its own context window) reads the extracts via paths and returns prose.
   Cap 5 sessions; exclude the current session; never reproduce tool I/O or thinking blocks.
   (See `references/session-forensics.md`.)
5. **Read-only on the WORLD; one git-ignored tick is the only write.** `/resume` reads code, issues, PRs,
   and the board but mutates none of them. Its **single write** is one re-entry saga tick that **REUSES
   the restored saga_id** (never a paraphrase-derived id). It mints a new saga **only** in the Tier-2
   no-saga branch. **Never `git add`** the tick — saga state is git-ignored, machine-local.
6. **Route, don't execute.** `/resume` reconstructs and then routes to the one command that owns the next
   phase, via the **shared** `../loop/references/dispatch-table.md` (referenced, never duplicated). The
   common case is `/work` (resume the round-N loop) or `/handoff` (let another session pick it up). It
   never builds, never files issues, and **never routes back to `/loop`** — no ping-pong.

## Interaction method

Use `AskUserQuestion` for choices from a known set (which saga thread when several match, resume-vs-fresh,
the reconciled-state confirmation, the route destination). Call `ToolSearch` with
`select:AskUserQuestion` first if its schema is not loaded. Ask one question per turn; prefer a concise
single-select. For open-ended discussion, ask inline.

In a channel session (`redis-channel` active), `AskUserQuestion` cannot be called — inline the choices in
your reply text instead. Follow the canonical channel-inline convention in
`infiquetra-lifecycle/skills/brainstorm/SKILL.md` (do not duplicate its wording here).

Use repo-relative paths in every routing tick and every reference to a committed doc. Absolute paths
break portability across machines and worktrees. (The Tier-2 scratch dir from `mktemp` is the one
deliberate absolute path — it is throwaway, machine-local, and never committed.)

---

## Phase 0 — Enter, scan, classify the tier

Capture the input and decide which tier the run is before reconstructing anything.

The input is a GitHub issue reference, a plan / doc path, a set of PR numbers, the word `resume`, or a
bare "reconstruct what happened" ask. Take it from command arguments or the active artifact. If empty,
ask: "What should I reconstruct? Point me at the issue, a plan/doc path, the PRs, or describe the work."

Scan the saga log to find in-flight candidates:

```bash
python3 plugins/infiquetra-lifecycle/scripts/saga.py scan
```

`scan` returns one candidate per saga (latest tick each), newest-first by filename, each surfacing
`lifecycle_phase` / `phase_status` / `status` / `destination` / `issue_ref` / `plan_path` / `branch` /
the orchestration pointer. Classify the run:

- **matched-saga** — a candidate matches the thread (`issue_ref`, `plan_path`, `branch`, or operator
  confirmation) -> **Tier 1** (Phase 1 -> 2 -> 3a -> 4 -> 5).
- **resolvable-issue** — no matching saga, but the input names a GitHub issue (or one resolves via
  `state.json.sagas[*].issue_ref` ending in `#N`) -> **Tier 1** via PR archaeology + the issue
  (Phase 2's `load_saga_context.py` / `saga.py context` path).
- **NEITHER** — no matching saga AND no resolvable issue -> **Tier 2** (Phase 3b), the last-resort JSONL
  session forensics.

---

## Phase 1 — Select the thread (Tier 1)

Pick the one saga thread to reconstruct and **capture its EXACT `saga_id`** — carry that literal id to
Phase 5; never re-derive it from a paraphrase of the task.

- If `scan` surfaced **one** matching candidate, select it.
- If **several** match, disambiguate with `AskUserQuestion` (single-select over the candidate list:
  `saga_id` + `lifecycle_phase` + `issue_ref` + `updated_at`).
- For an issue whose `issue-<N>` directory is absent, resolve the id via `state.json.sagas[*].issue_ref`
  ending in `#N` — the id is **sticky**; **never** rename the directory (slug-instability guard,
  `../../references/saga-spec.md` §2.3 / §2.1).
- If **no** candidate matches **and** there is **no** resolvable issue, fall through to **Tier 2**
  (Phase 3b).

---

## Phase 2 — Tier 1: deep saga reconstruction

Read the **whole** trajectory, then the shared archaeology substrate, then the committed docs the ticks
point at.

**The all-ticks trajectory (the deeper-than-`/loop` capability):**

```bash
python3 plugins/infiquetra-lifecycle/scripts/saga.py ticks --saga-id <issue-N|task-slug>
```

`ticks` returns **every** tick oldest -> newest, full envelope each — the trajectory `/loop`'s
latest-tick-only `restore` cannot see (how the phase advanced, when blockers cleared, which questions got
answered). Reconcile the chain via the §6 snapshot semantics (`references/forensic-reconstruction.md`).

**The latest-tick anchor:**

```bash
python3 plugins/infiquetra-lifecycle/scripts/saga.py restore --saga-id <issue-N|task-slug>
```

`restore` is the current-state anchor (latest tick, cold, no git / network) — the starting point the
trajectory explains how you reached.

**The shared archaeology substrate** (the same calls `/loop` runs inline — substrate, not the
differentiator), for an issue-backed thread:

```bash
python3 plugins/infiquetra-lifecycle/scripts/load_saga_context.py --repo <owner/repo> --issue <N>
```

and / or the lower-level aggregate:

```bash
python3 plugins/infiquetra-lifecycle/scripts/saga.py context --repo <owner/repo> --issue <N>
```

Both aggregate round-tagged prior PRs (`reviewDecision` / `mergedAt` / round), ADR refs, and matching
journal sections. Then **read the committed `docs/*` the ticks point at** (`plan_path`,
`work_session_paths`, `review_paths`, `qa_paths`) — those are the durable truth; the cache is the anchor.

---

## Phase 3a — Reconcile and synthesize (Tier 1)

Reconcile the trajectory (all ticks) against the PR reality (`reviewDecision` / `mergedAt` / round) and
the committed docs, then produce the reconstructed state:

- **phase / destination** — the current `lifecycle_phase` / `phase_status`, the `destination` class.
- **blockers** — open vs cleared (a blocker a later tick or a merged PR resolved is **cleared**, not open).
- **open questions** — open vs answered (snapshot semantics: an answered question dropped off a later tick).
- **checks** — what tests / gates ran (latest snapshot).
- **next-step** — the one imperative resume anchor.

**Conflicts resolve toward the durable side.** If the cached `lifecycle_phase` says `work` but a PR for
this round is merged, the committed + GitHub state wins; the cache was stale. Surface every conflict
explicitly and confirm the reconciled state with the operator (Interaction method) before routing.

---

## Phase 3b — Tier 2: zero-save JSONL session forensics (FALLBACK ONLY)

Fires **only** when Phase 0 found **no saga AND no resolvable issue** — same-machine work that never
wrote a saga: raw sessions, pre-saga-adoption work, or a session that crashed before its first tick.
This is **not** the "fresh clone on a new machine" case (there the local session logs are simply absent —
fall back to the committed `docs/*` instead). Tier 2 is a slim Claude-only port of CE session forensics.

**The HARD context-safety guardrail:** the **orchestrator NEVER Reads or cats a raw `.jsonl` or a
skeleton file.** ONLY the generic synthesis agent reads skeletons, and ONLY via paths. **Never** paste
extract content into the dispatch prompt. (Full recipe + the CE guardrails: `references/session-forensics.md`.)

1. **Scratch dir** (throwaway, machine-local):

   ```bash
   SCRATCH=$(mktemp -d -t resume-sessions-XXXXXX)
   ```

2. **Discover** sessions for this repo, recency-ranked, capped at 5, current session excluded.
   `--exclude` is **mandatory** here — `discover_sessions.py` does **not** auto-detect the current
   session, so without the flag the current session is returned, extracted, and synthesized, violating
   the "Never analyze the current session" guardrail and burning a cap slot. `<current-session-id>` is
   this session's own `*.jsonl` basename under `~/.claude/projects/<repo>/` (drop the `.jsonl`):

   ```bash
   python3 plugins/infiquetra-lifecycle/scripts/discover_sessions.py --repo <repo-folder> --days <N> --exclude <current-session-id>
   ```

   The orchestrator reads only the path list + one-line `_meta` (no session content).

3. **Extract** each session's skeleton **file-mediated** to scratch (the orchestrator sees only the
   one-line `_meta` status — never the skeleton bytes):

   ```bash
   python3 plugins/infiquetra-lifecycle/scripts/extract_session_skeleton.py --output "$SCRATCH/<id>.skeleton.txt" < <session-file>
   ```

4. **Dispatch a GENERIC synthesis agent** (`Explore` / `Task` — this plugin has **no** `agents/` dir, so
   do **not** reference a named `ce-*` / `resume-session-historian` agent; mirror `/code-review` SKILL
   line 164). Pass the scratch **paths** + the historian guardrails as prompt text: read ONLY these
   paths, never read raw `~/.claude/projects/`, never invoke `Skill`, never reproduce tool I/O or thinking
   blocks, synthesize *what was tried / what didn't work / key decisions / related context*.

5. Optional explicit cleanup (the OS reclaims it regardless):

   ```bash
   rm -rf "$SCRATCH"
   ```

The synthesized prose feeds the route decision (Phase 4). Tier 2 writes a **new** saga in Phase 5 (the
one branch where minting is correct).

---

## Phase 4 — Route per the shared dispatch table

Route from the reconstructed `lifecycle_phase` / `phase_status` (Tier 1) or the synthesized state
(Tier 2) to the one command that owns the next phase, using the **shared**
`../loop/references/dispatch-table.md` (saga-spec §11). **Read** that table; do **not** restate it here —
one source of truth keeps `/loop` and `/resume` routing identical.

The common case is `/work` (resume the round-N loop on a `resume-ready` thread) or `/handoff` (when
another team / later session should pick the recovered work up). Announce the chosen command with a
one-line reason. **Never route back to `/loop`** — `/resume` is the forward path off `/loop`'s opt-in,
not a return ticket.

---

## Phase 5 — Write the one re-entry tick

Write exactly **one** re-entry tick recording the reconstructed state + the routing decision. **REUSE the
restored `saga_id` verbatim** — pass it through `--saga-id` (`save` accepts `--saga-id` as an explicit
override that **bypasses derivation entirely**, saga-spec §2.3; `--kind`/`--id` are then carried through
unchanged for the record). `save` mints a new saga dir unconditionally for any id it has not seen
(saga-spec §2.3 + §6), so a re-derived paraphrase forks a phantom thread — and so does the **prefix trap**:
`restore` exposes the prefixed `saga_id` (`task-<slug>`) AND the un-slugified original `id`; passing the
prefixed `saga_id` as `--id` re-derives `task-task-<slug>` and forks. The `--saga-id` override sidesteps
both. Use the EXACT id `restore` reported (`issue-<N>` / `task-<slug>`). Carry `lifecycle_phase`
**forward** (never clobber a consumer's phase); **never** set `next_round` (derived, §6.1):

```bash
python3 plugins/infiquetra-lifecycle/scripts/saga.py save \
  --saga-id <exact restored saga_id, e.g. issue-42 or task-refactor-the-thing> \
  --kind <issue|task> \
  --id <restored issue number, or the restored task id WITHOUT the task- prefix> \
  --lifecycle-phase <reconstructed-phase> \
  --phase-status <pending|in_progress|complete> \
  --status paused \
  --destination <plan-only|pr|merge|nonprod-deploy> \
  --next-step "<the one imperative resume anchor: the command being routed to>" \
  --issue-ref <owner/repo#N> \
  --plan-path docs/plans/YYYY-MM-DD-<topic>-plan.md \
  --rounds-seen "<observed rounds, pipe-separated; e.g. 1|2>" \
  --blockers "<reconciled open blockers, empty if cleared>" \
  --summary "<the reconstructed-state one-paragraph>"
```

- `--status paused` is the default re-entry disposition (or `active` if continuing in-session).
  Use `handed-off` **only** when routing to `/handoff` — and then also build the envelope
  (`handoff_envelope.py`, per `/loop`'s Phase 4.2).
- Minting a **new** saga is correct **only** in the Tier-2 no-saga branch (there is no restored id to
  reuse). In Tier 1, always reuse via `--saga-id` — for Tier 2, omit `--saga-id` and let derivation mint
  the fresh id from `--kind`/`--id`.
- **Never `git add`** the tick.

---

## Boundary negatives

`/resume` reconstructs and routes. It does **NOT**:

- build, test, or open / merge a PR (-> `/work`);
- file SDLC issues (-> `/handoff` / `sdlc-manager`);
- deploy (-> `infiquetra-deploy`);
- add an `agents/` dir or a custom subagent — Tier 2 uses **generic** `Explore` / `Task` agents
  (mirror `/code-review` SKILL line 164);
- re-port gstack's context save/restore — that **is** the saga (`scripts/saga.py`), already shipped;
- adopt a `[gstack-context]` commit trailer or any commit-side state;
- duplicate the dispatch table — it **references** `../loop/references/dispatch-table.md`;
- route back to `/loop` — no `/loop` <-> `/resume` ping-pong;
- mutate code, issues, PRs, or the board — it is **read-only on the world**, with its one git-ignored
  re-entry tick as the sole write.

## Reference files

- `references/forensic-reconstruction.md` — Tier 1: the all-ticks read + §6 snapshot reconciliation, the
  differentiator boundary (shared substrate vs depth), the conflict-resolution rule citing the existing
  precedence, and the reconstructed-state output shape.
- `references/session-forensics.md` — Tier 2: the corrected same-machine-no-saga trigger, the
  discover -> rank -> cap-5 -> exclude-current pipeline, the paths-not-content context-safety contract,
  the scratch-dir + generic-agent dispatch recipe, and the CE synthesis guardrails verbatim.
