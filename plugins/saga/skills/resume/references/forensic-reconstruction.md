# Tier 1 — Forensic Saga Reconstruction

Tier 1 is `/resume`'s deep dig over a saga thread. It reads the **whole** tick chain (not the last frame),
reconciles it via the saga's full-snapshot semantics, layers in deeper PR archaeology, and resolves
conflicts against the durable source of truth. It runs whenever a matching saga or a resolvable issue
exists; Tier 2 (`session-forensics.md`) is the fallback only when neither does.

## What makes Tier 1 deeper than /loop (the differentiator boundary)

`/loop` already restores the **latest** tick (`saga.py restore`) and runs the cold-context substrate
inline — `load_saga_context.py` + reading `docs/*` (`../../loop/references/drive-and-resume.md`, the
inline cold reconstruction). Those are **shared substrate**, NOT the differentiator. `/resume` does three
things on top, and those three are the depth:

1. **Read ALL ticks**, oldest -> newest — the full trajectory of how the thread moved, which the
   latest-tick-only `restore` cannot see.
2. **Deeper PR archaeology** — reconcile the trajectory against every round-tagged PR's `reviewDecision`,
   `mergedAt`, and round number.
3. **Explicit conflict reconciliation** — when the cache disagrees with the durable side, surface it,
   resolve it by the precedence rule below, and confirm with the operator.

## The all-ticks read

```bash
python3 plugins/saga/scripts/saga.py ticks --saga-id <issue-N|task-slug>
```

`ticks` returns **every** tick for the saga, oldest -> newest, the full envelope of each (frontmatter +
body). It orders purely by filename (`envelope_sort_key`), never `mtime` — the same ordering `restore` and
`scan` use (saga-spec §5.2). The latest-tick anchor is still worth reading as the current-state baseline:

```bash
python3 plugins/saga/scripts/saga.py restore --saga-id <issue-N|task-slug>
```

`restore` is the *destination* of the trajectory; `ticks` is the *path* that explains how the thread got
there. Read both.

## Reconciling the chain (saga-spec §6 snapshot semantics)

Each tick is a **full snapshot**, not a delta — lists REPLACE, they never union (saga-spec §6). So the
trajectory is read by diffing snapshots across ticks:

- **Answered questions drop off.** An `open_questions` entry present in an earlier tick but absent from a
  later one was **answered / resolved**, not lost. Do not resurrect it as open.
- **Cleared blockers vanish.** A `blockers` value that goes from non-empty to empty across ticks was
  **cleared**. Treat it as cleared, not open.
- **Phase regression is a signal.** If `lifecycle_phase` or `phase` moves *backward* across ticks (e.g.
  `work` -> `plan`), that is a real event — a re-plan, a reverted round, a rejected review — worth calling
  out in the reconstructed summary, not smoothing over.
- **Round growth** is read from `rounds_seen` across ticks; `next_round` is derived (`max(rounds_seen)+1`,
  saga-spec §6.1) — never assert it from a count of PRs alone.

## Deeper PR archaeology

The shared substrate calls aggregate the round-tagged PRs already:

```bash
python3 plugins/saga/scripts/load_saga_context.py --repo <owner/repo> --issue <N>
python3 plugins/saga/scripts/saga.py context --repo <owner/repo> --issue <N>
```

Both return `prior_prs` (number, state, `mergedAt`, `reviewDecision`, round), `rounds_seen` / `next_round`,
`adr_refs`, and matching journal sections. A missing `gh` no-raises to an empty PR list (saga-spec §7) —
offline reconstruction still works off the saga + committed docs. Tier 1's archaeology is reconciling each
round's PR outcome against the matching tick: a round whose PR is `MERGED` is done regardless of a stale
cached `phase_status`.

## The conflict-resolution rule (inherited precedence — do not reinvent)

When the git-ignored saga cache disagrees with the durable side, the durable side wins. This is the
**existing** precedence, inherited so `/loop` and `/resume` reconcile identically:

> Committed `docs/*` + GitHub issue / PR state are authoritative; the git-ignored
> `.claude/saga/` saga cache is the anchor, not the authority.
> — `../../loop/references/drive-and-resume.md` lines 108-111 + `../../../references/saga-spec.md` §10.

Concrete applications:

- Cached `lifecycle_phase: work` but the round's PR is merged -> the thread is past `work`; cache stale.
- Cached open `blockers` but a merged PR / a later tick cleared it -> blocker is **cleared**.
- Cached `branch` disagrees with the live branch -> git is authoritative (saga-spec §1.1); cache is for
  offline display only.

Surface every conflict explicitly and confirm the reconciled state with the operator before routing —
never silently overwrite or silently trust.

## The reconstructed-state output shape

Tier 1 produces a single reconciled state, ready to route on:

- **phase** — reconciled `lifecycle_phase` / `phase_status` (cache vs PR vs docs).
- **destination** — the `destination` class (`plan-only` / `pr` / `merge` / `nonprod-deploy`).
- **blockers** — open vs cleared, after reconciliation.
- **open questions** — open vs answered, after snapshot diffing.
- **checks** — tests / gates run (latest snapshot).
- **next-step** — the one imperative resume anchor (the command being routed to).

This shape feeds Phase 4 (route via the shared dispatch table) and Phase 5 (the one re-entry tick, which
reuses the restored `saga_id`).
