# Experiment loop

The condensed rigor of `ce-optimize`'s loop, adapted for the saga off-chain engine. This
is a **single-source port** of the source spine; the git-worktree-per-experiment, parallel /
`max_concurrent`, and auto-commit / auto-merge-of-experiment-branches machinery is **SHED** from the
default path and re-enters only by an explicit operator-choice escalation. `/optimize` keeps **zero new
Python** — the orchestrating agent parses the YAML natively and does the arithmetic.

---

## The optimization spec (condensed schema)

The spec is the contract for a run. Written to `.claude/saga/optimize/<slug>/spec.yaml`
at Phase 1 and immutable during the run.

```yaml
name: <kebab-case slug>                # safe for paths
description: <human-readable goal>
metric:
  primary:
    type: hard | judge                 # hard = number from the command; judge = LLM-as-judge
    name: <metric key in the command's JSON output; for type: judge, the field the judge returns in its JSON, not a command key>
    direction: maximize | minimize
    target: <number | null>            # optional; loop stops when reached
  degenerate_gates:                    # >= 1 REQUIRED — cheap boolean rejects, run first
    - name: <metric key>
      check: ">= 0.0"                  # operators: >= <= > < == !=
      description: <what this gate catches>
  diagnostics:                         # logged, never gated
    - name: <metric key>
  judge:                               # REQUIRED when type: judge
    rubric: <multi-line rubric; must instruct the judge to return JSON>
    sample_size: 10
    stratification:                    # optional buckets for sampling the output space
      - { bucket: <name>, count: <n> }
    batch_size: 5
    minimum_improvement: 0.3           # judge-score gain required to accept (sample-composition variance)
    max_total_cost_usd: 5             # judge-budget cap; null only with explicit approval
measurement:
  command: <shell cmd that emits JSON to stdout with all gate + diagnostic keys>
  timeout_seconds: 600
  stability:
    mode: stable | repeat              # stable = run once; repeat = run N times and aggregate
    repeat_count: 5
    aggregation: median | mean | min | max
    noise_threshold: 0.02              # hard-metric gain must exceed this to count as real
scope:
  mutable:   [ <paths the experiment MAY change> ]    # >= 1 entry
  immutable: [ <paths it MUST NOT — list the measurement harness here> ]   # >= 1 entry
stopping:
  max_iterations: 100
  max_hours: 8
  plateau_iterations: 10
  target_reached: true
```

**SHED from the source** (do **not** include in the default spec; re-add only via team-execution
operator-choice if the operator escalates to parallel fan-out): the `execution` block
(`mode: parallel`, `backend: worktree`, `max_concurrent`), the `parallel` block (port parameterization,
shared files, worktree budget), and `max_runner_up_merges_per_batch`. The default engine is **serial,
in-working-state, one variable at a time**.

**Validation at Phase 1:** `name` is kebab-case; `metric.primary.type` is `hard` or `judge`; if `judge`,
the `judge` block exists with a rubric; **at least one** degenerate gate; `measurement.command` is
non-empty; `scope.mutable` and `scope.immutable` each have **at least one** entry; gate operators are
valid; the in-scope working tree is clean.

---

## Baseline discipline

Measure the current code **before any change** and seed `best` from it (iteration 0).

- **`stable` mode** — run the harness once, trust the result. For a stable, deterministic metric.
- **`repeat` mode** — run the harness `repeat_count` times, aggregate by the configured method, and
  **calculate variance**. If variance exceeds `noise_threshold`, **warn the user** and suggest a higher
  `repeat_count`. Use this for any noisy signal (reliability, latency under load, flake rate).

For a **judge** metric, also score the baseline output to establish the starting judge score. A baseline
you cannot trust makes every later "improvement" meaningless — invest here.

---

## Hypothesis backlog shape

10-30 hypotheses, each:

```yaml
- description: <what to try>
  category: <metric class or domain category, e.g. algorithm, preprocessing, caching>
  priority: high | medium | low
  required_deps: [ <new packages, if any> ]
```

Prefer **diversity** when selecting a batch (different categories), and within a category prefer high
priority first. More hypotheses are generated between batches from the strategy digest, not from memory.

---

## Bounded one-variable experiments

Per experiment, in order:

1. **Change ONE variable** within mutable scope. Never touch immutable scope.
2. **Measure** (single or repeat-aggregate per the stability mode).
3. **Degenerate gates FIRST.** If any hard gate fails -> outcome `degenerate`, skip the judge, revert.
4. **Judge only if gates pass** (judge metrics): sample (stratified if configured), score against the
   rubric, aggregate.
5. **Append the result (outcome, gates, gates_passed, diagnostics, and — for judge metrics — judge scores) to the log IMMEDIATELY, then verify** by re-reading (see the write rule below).
6. **Rank** against the current best and decide the terminal outcome.

---

## The crash-safe append-only experiment log

Written to `.claude/saga/optimize/<slug>/experiment-log.yaml`. **This file on disk is
the single source of truth** — the conversation context is expendable.

```yaml
spec: <slug>
run_id: <timestamp-based id>
started_at: <ISO 8601>                  # recorded once at baseline; the parseable wall-clock anchor the `max_hours` stop reads after a resume (run_id is identity, not a clock)
baseline:
  timestamp: <ISO 8601>
  gates: { <gate>: <value>, ... }
  diagnostics: { <diag>: <value>, ... }
  judge: { <score fields>, ... }       # judge metrics only
experiments:                           # APPEND-ONLY; one entry per experiment
  - iteration: 1
    batch: 1
    hypothesis: <description>
    category: <class>
    outcome: kept | reverted | degenerate | error | timeout
    gates: { <gate>: <value> }
    gates_passed: true | false
    diagnostics: { ... }
    judge: { ... }                     # judge metrics only
    primary_delta: "+0.7"
    learnings: <what this taught us>
best:
  iteration: <n>                       # 0 = baseline snapshot before any keep
  metrics: { ... }                     # current best metric values
  judge: { ... }                       # judge metrics only
hypothesis_backlog:                    # remaining, not yet tested
  - { description: ..., category: ..., priority: ..., required_deps: [] }
```

### Outcome enum (semantics REDEFINED for the off-chain engine)

- **`kept`** — passed all gates and improved the primary metric past the threshold. Recorded as the
  **current best IN THE LOG** and **held in working state**. It is **NOT committed and NOT merged** here.
- **`reverted`** — did not improve past the threshold (or was worse). **Discarded from working state.**
- **`degenerate`** — a hard degenerate gate failed; judge skipped; reverted.
- **`error`** — the measurement command crashed or emitted malformed output; reverted.
- **`timeout`** — the measurement command exceeded `timeout_seconds`; reverted.

**DROPPED from the source enum:** `measured` (the transitional pre-evaluation state — the serial loop
evaluates each experiment before moving on, so it is unneeded), and the branch-merge / worktree states
`runner_up_kept` and `runner_up_reverted`. There is **no per-experiment commit** and **no `commit` field**
in the default engine. A winner becomes a real commit **only when it is routed to `/work`** to ship.

---

## Write-immediately-then-verify + checkpoint discipline

The autoresearch rule: **write each experiment result to the log the moment its metrics are known —
before evaluating the next experiment — then read the file back and confirm the entry is present.** A
results table shown to the user that was not written to disk first is a bug. The mandatory checkpoints:

| Checkpoint | File written | When |
|---|---|---|
| CP-0 | `spec.yaml` | Phase 1, after approval |
| CP-1 | `experiment-log.yaml` (with baseline + seeded `best`) | Phase 2 |
| CP-2 | `experiment-log.yaml` (hypothesis_backlog) | Phase 3 |
| CP-3 | `experiment-log.yaml` (append each experiment) | Phase 4, immediately after each measurement |
| CP-4 | `experiment-log.yaml` (finalized outcomes + `best`) + `strategy-digest.md` | Phase 4, after each batch |
| CP-5 | `experiment-log.yaml` (final state) | Phase 5 |

At each checkpoint: write the file, read it back, confirm the expected content, retry on failure. **Re-read
the log from disk at every phase boundary and before every decision** — never trust in-memory state across
a batch boundary or a compaction.

---

## Strategy digest

Written between batches to `.claude/saga/optimize/<slug>/strategy-digest.md`: categories
tried (with kept/reverted counts), key learnings, the exploration frontier (what is untried), and current
best vs baseline. The agent reads the **digest** (not the full log, not its memory) when generating the
next round of hypotheses — this keeps context lean over a long run. The narrative record of any
operator-choice backend escalation also lives here.

---

## The seven stopping rules

Stop the loop if **ANY** is true:

1. **Target reached** — `target` is set and the primary metric reaches it for the configured direction.
2. **Max iterations** — total experiments run >= `max_iterations`.
3. **Max hours** — wall-clock since `started_at` (read from the log) >= `max_hours`.
4. **Judge budget exhausted** — cumulative judge spend >= `max_total_cost_usd` (judge metrics).
5. **Plateau** — no improvement for `plateau_iterations` consecutive experiments.
6. **Manual stop** — the user interrupts; save state and proceed to wrap-up.
7. **Empty backlog** — no hypotheses remain and no new ones can be generated.

---

## Run-directory layout

All run state lives under `.claude/saga/optimize/<slug>/` — **git-ignored, machine-local,
resumable by re-read**:

```
.claude/saga/optimize/<slug>/
├── spec.yaml              # the optimization spec (immutable during the run)
├── experiment-log.yaml    # the single source of truth — baseline + every experiment + best + backlog
└── strategy-digest.md     # compressed cross-batch learnings for hypothesis generation
```

On resume (Phase 0), read **all** state from `experiment-log.yaml` on disk — never rely on in-memory
context from a prior session.

---

## The durable split

Run-directory state is machine-local scratch and does not travel with a commit. Two durable sinks survive
the run:

- **The engineering-journal `LEARNINGS.md`** — a generalizable winning strategy (Evidence / Mechanism /
  Generalizable rule). The transferable lesson, kept forever.
- **An optional `docs/optimize/<date>-<slug>.md`** shareable summary — baseline -> final and the key wins.
  **Not** auto-discovered by `/handoff` (its classifier does not key on `docs/optimize/`); route a win by
  **naming the artifact path** or summarizing the change, never by assuming `/handoff` picks it up.

---

## Operator-choice fan-out note

The default loop is **serial**. For **independent experiment fan-out** — many hypotheses that do not share
output — **OFFER** a backend per `../../../references/operator-choice.md` (the narrow default offer:
`inline` and `team-execution`; `cc-workflows-ultracode` only on explicit invocation). `/optimize`
writes **no saga**, so the chosen backend is recorded **NARRATIVELY** in the strategy digest (operator-choice
§6 — a non-saga-writer records the choice in prose, never via `saga.save`). Never auto-spawn a backend.
