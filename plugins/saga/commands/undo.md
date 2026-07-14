---
name: undo
description: Replay the inverse of the last reversible mutation(s) from the undo ledger
argument-hint: "[count, default 1]"
---

Replay the inverse of the most recent reversible mutation(s) recorded by the mid-run
adjustment envelope's act-log-inverse-notify path (#372). Reversible mutations
(mission-control board/label/issue moves; saga branch/PR steps) proceed without pausing and
write a proven inverse to the undo ledger; `/undo` replays those inverses (LIFO).

## Instructions

1. Read the pending-undo records with
   `python3 plugins/saga/scripts/undo_ledger.py --repo-root . show` (schema + registered op set
   documented in `plugins/saga/references/adjustment-envelope.md`).
2. For the last `$ARGUMENTS` (default 1) record(s), take each record's computed `inverse` action
   and apply it to restore the pre-op state, then `undo_ledger.undo(ledger, state)` pops the
   replayed record(s) off the ledger tail so the ledger stays truthful.
3. Route any gh-write inverse (a board/label/issue move-back) through **mission-control** — saga
   never calls `gh issue`/`gh project` directly (the write-ownership lane). Saga-local inverses
   (delete a created branch, close an opened PR) replay directly.
4. An operation with **no registered inverse** was never recorded as reversible; there is nothing
   for `/undo` to replay — those operations went through a gated pause instead (R11).
5. Surface what was undone (op type, target, before→after→restored) to the operator.

Arguments provided to the command:

`$ARGUMENTS`
