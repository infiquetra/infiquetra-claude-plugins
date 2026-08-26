---
title: Orchestrate wait-debounce test still load-sensitive: wait_calls upper bound flakes under CI load
repo: infiquetra-claude-plugins
type: defect
team: campps
project: operations
status: Idea
labels: defect, needs-plan
risk: low
mode: standard
handoff_maturity: resume-ready
---

# Orchestrate wait-debounce test still load-sensitive: wait_calls upper bound flakes under CI load

### Objective
Issue #846 made two Orchestrate concurrency tests deterministic, but its repair to
tests/test_orchestrate_wait_debounce.py::TestFallbackProcessContract::test_restarts_share_one_monotonic_deadline
replaced a load-sensitive minimum call count with a bounded RANGE whose upper bound is still
load-sensitive. On a busy GitHub Actions runner the test produced 11 wait calls and failed:

  assert 1 <= len(wait_calls) <= 10
  E  AssertionError: assert 11 <= 10
  tests/test_orchestrate_wait_debounce.py:336

Observed on pull request 861 for issue #818, a Mission Control documentation change whose diff
contains no reference to that file. A rerun of the same job on the same commit passed, confirming a
load-sensitive flake rather than a regression. Because the assertion now lives on main, any pull
request in this repository can red on it intermittently.

The fix is narrow: the upper bound must express the contract the test actually cares about — that
restarts share one monotonic deadline and timeouts strictly decrease — without asserting a call
count that varies with scheduler pressure. Issue #846's own accepted approach for the sibling test
was to assert elapsed-deadline behaviour rather than call counts; the same treatment applies here.

### Intent
Make `test_restarts_share_one_monotonic_deadline` assert the contract it actually cares about —
that restarts share one monotonic deadline and that successive `--timeout` values strictly
decrease — without asserting any call count that varies with scheduler pressure. Issue #846 already
applied exactly this treatment to the sibling test in the same file, asserting elapsed-deadline
behaviour and upper bounds rather than a call count; this unit finishes the job on the test #846
left half-converted.

### Out-of-scope / non-goals
- No production change to `orchestrate.py`. This is a test-assertion defect, not a runtime defect.
- No retry, sleep, or timing-tolerance framework, and no `pytest` plugin or fixture library.
- No change to the sibling test `test_atomic_claim_has_one_winner`, which #846 already fixed.
- No widening of the wait/debounce behaviour under test; the contract stays as it is.
- Do not simply raise the upper bound from 10 to a larger number — a bigger load-sensitive
  constant is the same defect with a longer fuse.

### Files expected to change
- `tests/test_orchestrate_wait_debounce.py`
- `docs/engineering-journal/LEARNINGS.md`

### Tests to add or update
- `tests/test_orchestrate_wait_debounce.py::TestFallbackProcessContract::test_restarts_share_one_monotonic_deadline`
  — replace the `1 <= len(wait_calls) <= 10` bound with assertions on deadline monotonicity and
  strictly decreasing `--timeout` values.
- Add a case that injects deliberate scheduling skew producing many more wait calls than the old
  bound allowed, and prove the repaired test still passes while the old assertion would have failed.

### Context library links
- Parent orchestration issue: infiquetra/infiquetra-claude-plugins#847
- Predecessor whose fix this completes: infiquetra/infiquetra-claude-plugins#846
- Observed failure: pull request 861 (issue #818), job 98274878327, `assert 11 <= 10`
- Sibling defect class already fixed in this run: infiquetra/infiquetra-claude-plugins#839
  (terminal-width-dependent assertions)

### Acceptance criteria
- [ ] The focused test passes twenty consecutive times under load:
      `for i in $(seq 20); do uv run pytest tests/test_orchestrate_wait_debounce.py::TestFallbackProcessContract::test_restarts_share_one_monotonic_deadline -q || break; done`
      — expected: twenty runs, all passing, no failures.
- [ ] No call-count upper bound remains in the repaired test:
      `grep -n 'len(wait_calls)' tests/test_orchestrate_wait_debounce.py`
      — expected: no line asserting an upper bound on the number of wait calls.
- [ ] The strictly-decreasing timeout contract is still asserted:
      `grep -c 'earlier > later' tests/test_orchestrate_wait_debounce.py`
      — expected: at least 1.
- [ ] Mutation proof — reinstating `1 <= len(wait_calls) <= 10` alongside the injected scheduling
      skew fails, while the repaired test passes:
      `uv run pytest tests/test_orchestrate_wait_debounce.py -q`
      — expected: exit code 0 as written; non-zero with the old bound restored.
- [ ] The module and its sibling concurrency module are green:
      `uv run pytest tests/test_orchestrate_wait_debounce.py tests/test_liveness_events.py -q`
      — expected: exit code 0.

### Verification
```bash
# Focused test, twenty consecutive runs
for i in $(seq 20); do
  uv run pytest tests/test_orchestrate_wait_debounce.py::TestFallbackProcessContract::test_restarts_share_one_monotonic_deadline -q || break
done

# No surviving call-count upper bound
grep -n 'len(wait_calls)' tests/test_orchestrate_wait_debounce.py

# Whole module and the sibling concurrency module
uv run pytest tests/test_orchestrate_wait_debounce.py tests/test_liveness_events.py -q

# Repository gate (backgrounded per repository policy)
GATE_LOG_DIR=/tmp/gate-846b bash scripts/gate.sh > /tmp/gate-846b.log 2>&1 &
cat /tmp/gate-846b/result.txt
```

### Handoff maturity
resume-ready

### Suggested next action
Use `/work <issue>` to resume from the captured work state.

### Source context
- Source: docs/sdlc-issue-drafts/2026-08-26-orchestrate-wait-debounce-test-still-load-sensit-2.md
- Source type: prepared-draft
- Source title: Orchestrate wait-debounce test still load-sensitive: wait_calls upper bound flakes under CI load

### Recommended Tier Band
opus/high

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/863
- Number: 863
- Created at: 2026-08-26T18:51:18.244539+00:00

