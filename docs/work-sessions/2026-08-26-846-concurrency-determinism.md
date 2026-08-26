# Work session — deterministic Orchestrate concurrency tests (#846)

**Saga:** `issue-846` · **Plan:** `docs/plans/2026-08-26-improve-claude-plugins-847-run-plan.md` ·
**Branch:** `orch/orch-2026-08-26-847-847-s1-846` · **Destination:** pr ·
**Backend:** `inline` · **Unit:** U3 (S1)

## Summary of Changes

Repaired test synchronization in the two load-sensitive Orchestrate concurrency tests without changing production code or weakening test semantics:

1. **`tests/test_liveness_events.py::test_atomic_claim_has_one_winner`**
   - Synchronized both competing claim threads using a timeout-bounded `threading.Barrier(2, timeout=5.0)` after each contender has polled and observed the candidate `reping` fact and before either claims.
   - Bounded `Future.result(timeout=5.0)` retrieval to prevent test suite hangs and fail diagnostically on broken barriers or unexpected exceptions.
   - Introduced deliberate scheduling skew (`claim-b` delayed by 20ms before polling) to prove that uncoordinated execution in the old shape leads to candidate starvation, while the barrier ensures reliable observation and concurrent claim contention.
   - Verified that exactly one claim wins ("won") and the other catches the conflict `LivenessEventError` ("lost"), writing exactly one `reping-intent` record to the ledger.

2. **`tests/test_orchestrate_wait_debounce.py::TestFallbackProcessContract::test_restarts_share_one_monotonic_deadline`**
   - Adjusted `wait_delays="0.05"` and asserted `2 <= len(wait_calls) <= 10` alongside strictly decreasing timeouts (`strict=True`) and elapsed monotonic bounds (`0.8 <= elapsed <= 2.0`) to prove shrinking deadlines across actual restarts under load without brittle timing.
   - Asserted `timeout_values[-1] < timeout_values[0]` directly verifying remaining budget attenuation across restarts.

3. **`docs/engineering-journal/LEARNINGS.md`**
   - Appended a dated learning entry under `## 2026-08-26` capturing root causes, evidence, fixes, and the generalizable rule for rendezvous barrier testing.

## Checks Run & Verification

- **20 consecutive focused test runs:**
  ```bash
  for i in {1..20}; do
    uv run pytest tests/test_orchestrate_wait_debounce.py::TestFallbackProcessContract::test_restarts_share_one_monotonic_deadline tests/test_liveness_events.py::test_atomic_claim_has_one_winner -q || exit 1
  done
  ```
  Passed 20/20 iterations consecutively.
- **Ruff linting:**
  `uv run ruff check tests/test_orchestrate_wait_debounce.py tests/test_liveness_events.py` — clean.
- **Git diff check:**
  `git diff --check` — clean.

## Next Steps

Commit changes, push branch, and open PR linked to #846. Code Review is handled by the Orchestrate run's typed Grok Code Review controller.
