---
name: resume
description: Heavy forensic reconstruction of an Infiquetra work thread — whole-trajectory saga + PR archaeology, or last-resort session forensics — then route to the owning command
argument-hint: "[issue, plan path, PRs, or 'resume' / 'reconstruct what happened']"
---

Reconstruct an in-flight Infiquetra work thread in depth, then route. `/resume` is the lifecycle's
**heavy forensic reconstruction engine** — the deep half beside `/loop`'s lightweight restore. It is
**read-only on the world**; its single write is one git-ignored re-entry saga tick.

## Instructions

1. Load `saga/skills/resume/SKILL.md` and run its tiered flow:
   - **Tier 1 (default)** — saga-anchored deep reconstruction: read the **whole** tick chain
     (`saga.py ticks`, not just the latest frame `restore` reads), layer in PR archaeology
     (`load_saga_context.py` / `saga.py context`) and the committed `docs/*` the ticks point at, then
     **reconcile conflicts explicitly** (committed `docs/*` + GitHub win over the stale cache).
   - **Tier 2 (fallback only — no saga AND no resolvable issue)** — a slim, Claude-only port of CE
     session forensics: discover local JSONL sessions, extract skeletons **file-mediated** to a scratch
     dir, and dispatch a **generic** synthesis agent to read the extracts.
2. **Route** the reconstructed thread per the **shared** `skills/loop/references/dispatch-table.md`
   (referenced, never duplicated) — commonly to `/work` (resume the round-N loop) or `/handoff`. Never
   route back to `/loop`.
3. Write **one** git-ignored re-entry tick that **reuses the restored `saga_id`** (`saga.py save`,
   `--status paused` / `active`, or `handed-off` when routing to `/handoff`). Minting a new saga is
   correct **only** in the Tier-2 no-saga branch. Never `git add`.

## Boundary negatives

- The **orchestrator never Reads or cats a raw `.jsonl` or a skeleton file** — only the generic synthesis
  agent reads extracts, only via paths.
- Tier 2 uses **generic** `Explore` / `Task` agents — **no** custom subagent, **no** `agents/` dir
  (mirrors `/code-review`).
- The re-entry tick **reuses the restored `saga_id`**, never a re-derived paraphrase.
- `/resume` does **not** build / test / PR (-> `/work`), file issues (-> `/handoff` / `mission-control`),
  deploy (-> `deploy`), duplicate the dispatch table, or route back to `/loop`.

Arguments provided to the command:

`$ARGUMENTS`
