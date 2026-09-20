# The benchmark loop — propose-not-commit gate (#459 R2, T2-F1-7)

The benchmark harness (`scripts/engine_benchmark.py` + `references/benchmark-suite.yaml`) is the
fleet's **active** measurement of an `engine-registry.yaml` capability claim: it runs a fixed,
versioned eval suite against a live engine and compares the measured rating to the authored one.
It is distinct from the passive dispatch telemetry (`run_ledger.py` `engine` facts) and from the
Elo reducer (`capability_elo.py`, which learns from live reconciliation outcomes) — both feed
`/retro` proposals; neither substitutes for the other.

## The hard rule

**A benchmark result never edits the registry.** No code path in `engine_benchmark.py` opens
`engine-registry.yaml` for writing; a measured-vs-claimed contradiction terminates in a
`registry_calibration_proposal.v1` cell that `/retro` Phase 5(f) surfaces with
propose-diff-and-wait, and only a **human** applies the hand-edit. This is the
`{#external-engines-never-gatekeepers}` (#283) posture applied to the registry's own data — a PR
that writes the registry directly from a benchmark (or any other earned-ratings signal) fails
review. `tests/test_saga_retro_calibration.py::test_proposal_only_never_writes_registry` is the
durable byte-identity guard.

## Running the harness

Operator-invoked only (issue non-goal: no standing, scheduled calibration ceremony — calibration
runs on `/retro`'s cadence or an explicit CLI invocation):

```bash
python3 plugins/saga/scripts/engine_benchmark.py run \
  --engine codex/gpt-5.5-xhigh \
  --capability adversarial-review \
  --runner-cmd 'codex exec --read-only' \
  --root . --ledger --json
```

- `--runner-cmd` is the live lane: each probe prompt goes to the command's stdin; the engine's
  reply is read from stdout. Real query, real engine, human-triggered.
- `--ledger` appends one `benchmark` run fact (hash-chained, `run_fact.v1`) so `/retro`'s
  calibration aggregation (`engine_calibration.py`) can consume the measurement later; without
  it the run performs no I/O beyond the engine call.
- Library use injects `runner: Callable[[EngineEntry, str], str]` into `run_suite` — the test
  seam, and the only seam.

## Suite versioning (immutable `suite_id`)

- A suite is identified by its `suite_id` (e.g. `adversarial-review-v1`). **Editing, adding, or
  removing a probe requires a NEW `suite_id`** (`-v2`, ...). Measured ratings are only comparable
  within one `suite_id`; the ledger fact carries the `suite_id` so history stays honest.
- Graders are **deterministic string checks only** (`contains`, `regex`, `json-parses`). Never an
  LLM-graded probe: an external engine must not become the judge of another engine's rating
  (#283). Nuance belongs to the human reading the proposal, not to the grader.

## Threshold semantics

`thresholds: {STRONG: 0.8, MODERATE: 0.5}` are pass-share floors: pass share `>= STRONG` measures
`STRONG`; `>= MODERATE` measures `MODERATE`; below measures `WEAK`. The `STRONG` floor must
exceed the `MODERATE` floor (the loader enforces this).

## From contradiction to applied edit

1. The harness measures a rating that disagrees with the authored claim → it emits a
   `registry_calibration_proposal.v1` **cell** (and, with `--ledger`, a `benchmark` fact carrying
   `contradicts: true`).
2. `/retro` Phase 1.11 reads the aggregated calibration report (`engine_calibration.py report`),
   which chain-verifies the ledger and folds benchmark contradictions in with the staleness /
   Elo / SPC signals.
3. `/retro` Phase 5(f) renders the diff preview and asks the operator (apply / skip / modify).
4. **An "apply" answer means the operator (or a follow-up `/plan`) performs the hand-edit** of
   `engine-registry.yaml` — the rating and a fresh `last_validated` — outside `/retro`. No
   automation applies it.
