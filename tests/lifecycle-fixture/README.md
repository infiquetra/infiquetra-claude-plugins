# Lifecycle CLI regression

Owner: the repository's Saga maintainers. Entrypoint:
`tests/test_lifecycle_regression_harness.py`. The daily **Lifecycle Regression** workflow and
manual dispatch run this entrypoint, retaining the existing job ID and display name.

```bash
uv sync --frozen --extra dev --python 3.12
uv run --frozen pytest tests/test_lifecycle_regression_harness.py --no-cov -v -rA \
  --junitxml=lifecycle-regression-report.xml
# One independently runnable scenario:
uv run --frozen pytest tests/test_lifecycle_regression_harness.py --no-cov -k scenario_review
```

The workflow has a ten-minute job deadline, serializes runs per workflow/ref without cancelling
an active run, and uploads JUnit even after test failure (seven-day retention). Each CLI invocation
has a fifteen-second deadline. Collection errors and missing reports fail; no skips or credential
dependent paths can turn the scheduled run green. Merge context names and `ci.yml` are unchanged;
the ordinary full pytest discovery also includes this file.

## Current scenarios and assertions

Each test copies the tracked `seed/` into pytest's temporary directory and initializes an independent
Git repository with a real initial commit, isolated configuration/hooks/home, and no remotes. The
tracked seed has no `.git`. Only an explicit environment allowlist reaches subprocesses. Production
scripts run directly from this checkout through `sys.executable`, with the fixture as their working
directory; no production functions or CLIs are mocked. All writes stay in the temporary fixture.

| Scenario | Production CLI seams | Evidence checked independently on disk and through readers |
|---|---|---|
| `scenario_plan_to_work_appends_immutable_ticks` | `plan_artifact_conformance.py`, `saga.py save/restore/ticks` | Plan conformance; completed plan tick and plan pointer; a real source change/commit on a work branch; two distinct immutable tick envelopes; fresh branch/short HEAD/full last-commit SHA; chronological summaries; derived index |
| `scenario_review_result_crosses_store_and_gate_boundaries` | `review_result.py`, `run_record.py show`, `saga.py save/restore` | Real seeded diff; v2 result appended to a v1 run record and read by a new process; reviewed full revision, lens score, cycle and unit preserved; rendered comment bound to revision; gate and review pointers in both tick and restore; HEAD unchanged |
| `scenario_resume_reads_ticks_despite_corrupt_index` | `saga.py save/restore/scan/ticks` | Paused tick and next step survive a deliberately corrupt derived index; explicit active save appends rather than overwrites; index rebuilt and two ticks retained |

The plan, admission record, and lens verdict are deterministic **inputs**. These tests prove CLI
artifact contracts, not autonomous planning, code-review quality, admission policy, live roster
execution, merge/deploy behavior, or a full agent skill session. A stored `done` gate records the
supplied fixture verdict; the harness does not claim a lens evaluated the seeded diff.

Failure controls remove a required plan field and a unit marker (named findings and exit 1), pass
a missing plan directory (exit 2), delete a real saved tick (the same artifact assertion rejects it
and restore reports absent), omit a gate (both disk and restore assertions reject it), and supply an
unknown review schema or symbolic revision (exit 2, no comment and byte-identical run record).

## Why the original scenarios changed

The #428 implementation defined `spec-plan-work`, `code-review-gate`, `outcome-round-trip`, and
`worktree-reclaim`. Commit `0351415948b9ae70519f12605ea188a85169f8d7` removed that harness and its
fixtures during the #1030 Saga simplification, but left this workflow pointing to the deleted test.
At the audit baseline `acc99fe71e25ad8a898eace7033051a7f1c3079e`, invoking the missing path exits 4
with zero tests collected.

| Original obligation | Current disposition |
|---|---|
| Execution-spec JSON in `spec-plan-work` | The removed execution-spec engine is not restored. Validate the maintained inline plan document with the shipped plan-conformance CLI; persist plan/work ticks across a real branch and revision change. |
| Appended Saga log and `code-review-gate` | Retained and extended: inspect immutable envelopes, reader output, the current review-result/run-record boundary, a rendered comment, and gate pointers. |
| `outcome-round-trip` | The outcome coordinator, DAG, intent tokens, and outcome CLI were explicitly retired by #1030. Exercise the current Saga pause/restore/scan/active-save persistence seam, without claiming outcome/DAG equivalence. |
| `worktree-reclaim` | The managed outcome worktree ensure/reap machinery was explicitly retired by #1030. No managed worktree is opened, so there is no production reclamation claim. Each scenario uses its own temporary Git repository. |

The removal decision is recorded in
`docs/plans/2026-09-20-issue-1030-removals-and-saga-1-0-0-release-plan.md` (R1/R2);
the surviving lifecycle is described by `plugins/saga/docs/lifecycle.md`. Restoring the obsolete
schedule unchanged or replacing it with similarly named unit tests would leave the contract
misleading. This repair retains the daily CLI artifact obligation against supported behavior.

## Extending, diagnosing, and rolling back

Add a named `test_scenario_*` to the entrypoint, reusing the private `repo` fixture. Drive a shipped
CLI, reread its artifacts with independent assertions and a fresh reader process, and add a seeded
failure that proves those assertions or the CLI refusal can fail. Add deterministic inputs under
`seed/` only when necessary. Keep remote commands, agents, credentials and production mutation out
of the harness. Update this mapping when a seam is retired or replaced.

JUnit names each scenario/control and includes assertion diagnostics with the missing artifact,
finding, or failed CLI. For local output use `/tmp/lifecycle-regression-report.xml` to keep the
worktree clean. Host-wide full suites must take `/tmp/ci-efficiency-heavy.lock` during the CI audit
execution programme.

Rollback the repair commit with `git revert <repair-commit>`. This restores the known-broken daily
entrypoint, so an owner must supply a valid harness before accepting that rollback for a running
schedule. No plugin runtime behavior or release metadata changes in this package; no plugin version
bump is required. The coordinator owns review/merge and observing the first successful hosted daily
or manual run. Local evidence does not establish hosted scheduling or runner success.
