# Pulse manual verification — drive a real run, watch the surface update

The automated proof is `uv run pytest tests/test_pulse_telemetry.py -k drives_real_run`
(a real saga tick transition + real hash-chained ledger facts, asserted as a before/after
render diff). This recipe reproduces the same check by hand against live state.

1. **Start a disposable run.** In a scratch worktree, begin any small piece of work through
   `/work` (or write tick 1 directly):

   ```bash
   python3 plugins/saga/scripts/saga.py save --kind task --id pulse-drill \
     --lifecycle-phase work --phase 1 --phase-status in_progress
   ```

2. **Take the first snapshot.**

   ```bash
   python3 plugins/saga/scripts/pulse.py --project operations
   ```

   Observe: the drill saga listed with `phase=1 status=in_progress`; the ledger panel
   reporting its current chain verdict and fact counts; the board panel showing live
   Operations columns (or an explicit `unavailable (<reason>)` if `gh` is not authenticated —
   never an empty board).

3. **Advance the run.** Write the next tick (`--phase 2 --phase-status complete`). If the run
   dispatches an external engine call, `engine_dispatch` appends a real `engine` fact to the
   ledger as a side effect.

4. **Re-run Pulse** (or leave `--watch --interval 15 --iterations 20` running in another
   terminal). Observe the run row's phase change and, if facts were appended, the ledger
   fact-count/spend change. This is the DoD's "observe the surface reflect the run's state
   changing on refresh".

5. **Negative check (the explicit-degrade contract).** Move the ledger file aside:

   ```bash
   mv "$(git rev-parse --git-common-dir)/saga-run-facts/run-facts.jsonl"{,.bak}
   python3 plugins/saga/scripts/pulse.py
   ```

   Observe `Ledger — no data yet`, **not** zeros. Restore the file afterwards:

   ```bash
   mv "$(git rev-parse --git-common-dir)/saga-run-facts/run-facts.jsonl"{.bak,}
   ```

6. **Clean up** the drill saga directory under `.claude/saga/sagas/task-pulse-drill/` (it is
   git-ignored, machine-local state).
