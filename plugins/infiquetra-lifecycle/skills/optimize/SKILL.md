---
name: optimize
description: Run a metric-driven Infiquetra optimization loop — define a measurable goal, baseline current behavior, generate a hypothesis backlog, run bounded one-variable experiments, measure each against hard degenerate gates before any LLM-judge, keep the best real improvement and revert the rest, and converge on the measurably-best version. Eight metric classes (perf, cost, reliability, agent-usability, security, quality/accuracy, developer-experience, maintainability). Off-chain and saga-untouched; it finds the winner, then routes it to /work to ship — it never commits, merges, or deploys. Triggers on "optimize this", "make it faster/cheaper", "tune this", "baseline and improve", "drive this metric to a target", or a perf finding handed in from /qa or /loop.
argument-hint: "[metric, workflow, or bottleneck]"
---

# Optimize

Ported from Compound-Engineering `ce-optimize` — the metric-driven iterative optimization loop is a
**single-source PORT** of that engine's spine (spec -> baseline -> hypothesis backlog -> bounded
one-variable experiments -> measure with hard degenerate gates BEFORE LLM-judge -> strategy digest ->
crash-safe append-only experiment log -> stopping rules). **agent-usability is an infiquetra-native
metric class (Jeff's angle), NOT a gstack port**; gstack `plan-tune` (a developer-psychographic
question-tuning coach) supplies no engine or mechanism here and is not ported. This is **NOT a balanced
two-engine merge** — it is a single-source port.

The default path SHEDS `ce-optimize`'s git-worktree-per-experiment isolation, its parallel /
`max_concurrent` fan-out, and its auto-commit / auto-merge of experiment branches. Those re-enter only
by an explicit operator-choice escalation (Phase 4), recorded narratively. The loop runs **serial and
in working state** by default; a winner becomes a real commit only when it is routed to `/work`.

## Position in the lifecycle

`/optimize` is **OFF-CHAIN, advisory, and saga-UNTOUCHED**. It is **not** a `LIFECYCLE_PHASE`, it never
advances `lifecycle_phase`, it writes **no** saga, and it **never blocks** `/loop`. It answers one
question: **"What is the measurably-best version of this, found by bounded experiment?"** Its durable
outputs are an engineering-journal `LEARNINGS.md` entry for a generalizable win and an optional
shareable summary; the winning code change itself routes onward to ship.

Its lane, vs its neighbors:

- **vs `/qa`** — `/qa` **GATES** a shipped change: it runs acceptance checks once, severity-bands the
  findings, and derives a one-shot ship-or-not verdict. `/optimize` **LOOPS** toward a measurable
  target: baseline -> experiments -> converge. The default routing rule, stated plainly:
  - "is this change good / secure enough to ship?" -> **`/qa`** (gate, one-shot verdict).
  - "iteratively drive this metric (including security-finding count, quality score) toward a target by
    experiment" -> **`/optimize`** (loop, baseline-to-converge).
- **vs `/pulse`** — `/optimize` is a **BOUNDED** experiment loop with a start, stopping rules, and an
  end. `/pulse` (future) is **CONTINUOUS** live telemetry. They are complementary; `/optimize` does not
  block on `/pulse` and does not stream.
- **vs `/work`** — `/optimize` finds the best version, then **ROUTES the winning change to `/work` to
  ship** it. It never ships in-engine: no PR, no merge, no commit of the winner inside this engine.

**Routes IN:** `/loop` (the router meets a "make this measurably better" ask), a `/qa` performance
finding, a `STRATEGY.md` key-metric that needs driving, or direct invocation.

**Routes OUT:** a confirmed win -> `/handoff` or `/work` or `/code-review`; a problem that is really a
design question (no experiment moves the metric) -> `/brainstorm`; a durable, generalizable win -> the
engineering-journal `LEARNINGS.md`.

Resolve any cross-command route through the lifecycle routing reference at
`loop/references/dispatch-table.md` (referenced by path; do not restate the routing table here).

## Core principles

1. **Metric-driven, scope-bounded — no spec, no loop.** Before any experiment runs there MUST be a
   primary metric + a direction (`maximize` / `minimize`) + an explicit mutable/immutable scope + at
   least one degenerate gate. A goal without a measurable metric and a bounded scope is a `/brainstorm`
   or `/strategy` question, not an optimization run.
2. **The log on disk is the single source of truth.** The conversation context is **not** durable
   storage; a results table shown to the user that was not written to disk first is a bug. Write each
   experiment result to the experiment log **immediately** after measurement, **verify by re-reading**
   the file, and **re-read the log at every phase boundary** before any decision. This is the autoresearch
   write-after-every-experiment discipline.
3. **Cheap hard gates before expensive judgment.** Run the hard **degenerate gates** first; only run the
   LLM-judge if the gates pass. A broken solution fails a cheap boolean check before it ever costs a judge
   call.
4. **One variable at a time; baseline first; beat the noise.** Establish the baseline before any change,
   change exactly one variable per experiment, and only **keep** a result whose improvement exceeds the
   measured noise threshold (hard metrics) or the `minimum_improvement` (judge metrics). A change that
   does not clear the noise floor is reverted.
5. **Eight metric classes.** perf, cost, reliability, agent-usability, security, quality/accuracy,
   developer-experience, maintainability. Each metric is measured as **hard** (a direct numeric, gated)
   or by **judge** (semantic quality), chosen per metric — see `references/metric-taxonomy.md`.
6. **Default bounded & serial; escalate by CHOICE.** The loop runs serial and in working state by
   default. For **independent experiment fan-out** it **OFFERS** `team-execution` /
   `cc-workflows-ultracode` per the operator-choice contract, recorded **narratively** (this engine
   writes no saga). It never auto-spawns a backend, never auto-commits, never auto-merges, never deploys.

## Interaction method

Use `AskUserQuestion` for choices from a known set — spec approval, the metric class, the execution
backend, and stop-vs-continue at a stopping-rule boundary. Call `ToolSearch` with
`select:AskUserQuestion` first if its schema is not loaded; a pending schema load is not a reason to
skip the question. Ask one question at a time; never silently skip a question. Use **free-form** for the
substantive content (the hypothesis backlog, the strategy digest, learnings) — menu options would
flatten them.

In a channel session (`redis-channel` active), `AskUserQuestion` cannot be called — inline the choices
in your reply text instead, following the canonical channel-inline convention in
`../brainstorm/SKILL.md` (do not duplicate its wording here).

Use repo-relative paths in everything you write — absolute paths break portability across worktrees.

---

## Phase 0 — Enter, parse, route by file state

Parse the optimization goal from `$ARGUMENTS` (a metric, a workflow, or a named bottleneck). If the
input is empty, ask: "What would you like to optimize? Name the metric or the workflow, or point me at
an optimization spec."

Derive a kebab-case `<slug>` from the goal and read the run directory
`.claude/infiquetra-lifecycle/optimize/<slug>/` to detect an in-flight run:

- **An experiment log exists** -> **RESUME.** Read **all** state from `experiment-log.yaml` on disk (do
  **not** trust any in-memory context from a prior session). Recover the current best, the tested
  hypotheses, and the remaining backlog from the log, then continue from where it left off (re-enter the
  loop at Phase 4). Announce: "Found an in-flight run — resuming from the experiment log."
- **No run directory / no log** -> **FRESH start.** Go to Phase 1. Announce: "No prior run — let's
  define the optimization."

## Phase 1 — Spec + scope (HARD GATE)

Load-or-create the optimization spec. Required (see `references/experiment-loop.md` for the condensed
schema):

- **primary metric** — name + direction (`maximize` / `minimize`) + optional target;
- **metric class** + whether it is measured **hard** or by **judge** (`references/metric-taxonomy.md`);
- **mutable scope** (files the experiments MAY change) and **immutable scope** (files they MUST NOT —
  always list the measurement harness here), each with at least one entry;
- **at least one degenerate gate** (a cheap boolean that rejects an obviously broken solution);
- **a clean-tree check** on the in-scope files — if any in-scope file has uncommitted changes, ask the
  user to commit or stash before proceeding.

Write the spec to `.claude/infiquetra-lifecycle/optimize/<slug>/spec.yaml`, verify it by re-reading, and
**present it for approval** via `AskUserQuestion`. **Do NOT proceed to Phase 2 without an approved spec
and a defined primary metric.** If the target is qualitative, recommend `judge`; if the user insists on
`hard` for a qualitative target, warn that it may optimize a misleading proxy.

## Phase 2 — Baseline

Measure the current code with the spec's measurement command. For a noisy signal, use the
**repeat-aggregate** mode (run N times, aggregate by median/mean/min/max, and warn if variance exceeds
the noise threshold); otherwise measure once. For a **judge** metric, also score the baseline output to
establish the starting judge score.

**Seed `best` from the baseline** (iteration 0). Write the initial `experiment-log.yaml` (top-level
`spec` / `run_id` / `started_at` / `baseline` / `experiments: []` / `best` / `hypothesis_backlog: []`), **verify by
re-reading**, then present the baseline metrics and the log path to the user.

## Phase 3 — Hypothesis backlog

Read the mutable-scope code to understand the current approach, then generate **10-30 hypotheses**, each
with: a **description** (what to try), a **class** (one of the eight metric classes or a domain category),
a **priority** (high / medium / low), and any **dependencies**. Include user-supplied hypotheses. Write
the backlog into `experiment-log.yaml`, **verify by re-reading**. More hypotheses can be generated later
from the strategy digest.

## Phase 4 — Bounded experiment loop

This phase repeats in batches until a stopping rule fires. Re-read the experiment log from disk at the
start of every batch.

**Select a batch** from the runnable backlog. **Serial default = batch size 1.** For **independent
experiment fan-out**, **OFFER** an execution backend HERE per `../../references/operator-choice.md`
(§3.2 — broad, independent, low-risk fan-out leans `cc-workflows-ultracode`; risky-and-parallel leans
`team-execution`); record the chosen backend **narratively** in the strategy digest (this engine writes
no saga — §6 of operator-choice). Never auto-spawn.

**Per experiment:**

1. Change **ONE variable** within mutable scope.
2. **Measure** (single, or repeat-aggregate for a noisy metric).
3. **Degenerate gates FIRST** — if any hard gate fails, mark the outcome `degenerate`, skip the judge,
   and revert.
4. **Judge only if the gates pass** (judge metrics only).
5. **Append the result to the experiment log IMMEDIATELY + verify** by re-reading — before evaluating
   the next experiment.
6. **Rank** against the current best.
7. **KEEP the best real improvement** — one that clears the noise threshold (hard) or
   `minimum_improvement` (judge). The kept change is recorded as the **current best IN THE LOG** and
   held in working state; it is **NOT committed or merged** here. **REVERT the rest** — discard them
   from working state.

After the batch, write the **strategy digest** (categories tried, what worked / failed, the exploration
frontier, current best vs baseline) and the updated backlog to disk; verify. Then **check the stopping
rules** (see `references/experiment-loop.md`): target reached / max_iterations / max_hours / judge-budget
exhausted / plateau / manual stop / empty backlog. If none fire, run the next batch; otherwise go to
Phase 5. At a stopping-rule boundary, offer stop-vs-continue via `AskUserQuestion`.

## Phase 5 — Wrap-up + route

Re-read the log from disk and summarize **baseline -> final** for the primary metric, the gates, and the
diagnostics, with the key kept experiments and their deltas.

**Durable capture:**

- **Generalizable win -> the engineering-journal `LEARNINGS.md`** — append a dated entry (Evidence /
  Mechanism / Generalizable rule) when the winning strategy transfers beyond this one run. A purely
  local, mechanical win with no transferable insight is skipped.
- **Optional shareable summary** -> `docs/optimize/<date>-<slug>.md`. **Note:** this summary is **NOT**
  auto-discovered by `/handoff` — `/handoff`'s classifier does not key on `docs/optimize/`. Route a win
  by **naming the artifact path explicitly** or by summarizing the change to the routed command; never
  imply `/handoff` auto-picks-up `docs/optimize/`.

**Route** per `loop/references/dispatch-table.md` (read it; never restate it): a confirmed win ->
`/handoff` / `/work` / `/code-review`; a design problem -> `/brainstorm`. A winner is committed or merged
**only when it is routed to `/work`** to ship. There is **NO saga write**. Never run `gh issue create` —
`sdlc-manager` owns issue bodies.

## Hard boundary

`/optimize` defines, baselines, experiments, measures, keeps-the-best, writes the log, and routes — then
stops. It does **NOT**:

- **commit, push, open / update / merge a PR, or deploy** — winners are routed to `/work` to ship;
- **auto-commit or auto-merge experiment branches** — the default loop holds the best in working state;
  the SHED worktree / branch-merge machinery returns only by explicit operator-choice escalation;
- **mutate GitHub** — `gh` is read-only here, and it does **NOT** run `gh issue create` (`sdlc-manager`
  owns issue bodies);
- **write or advance the saga** — it is off-chain: no `saga.py` invocation, no `--lifecycle-phase`;
- **add a new script or an `agents/` dir** — this is a markdown-only engine;
- **GATE like `/qa`** (it loops toward a target, not a one-shot ship verdict) **or stream like `/pulse`**
  (it is a bounded experiment loop, not continuous telemetry).

`optimize` / `measure` / `baseline` / `experiment` / `tune` / `keep` / `revert` are this engine's
identity verbs.

## Reference files

- `references/metric-taxonomy.md` — the eight metric classes with example metrics, measurement method,
  and hard-vs-judge per class; the three-tier hard-vs-judge model; gate operators; noise_threshold vs
  minimum_improvement; and the note that `/optimize`'s direct numeric metrics need no `/qa`-style
  risk-weighted scorer.
- `references/experiment-loop.md` — the condensed spec schema, baseline discipline, the hypothesis
  backlog shape, the bounded one-variable experiment procedure, the crash-safe append-only experiment-log
  schema (with the redefined `kept` / `reverted` semantics), the write-immediately-then-verify rule, the
  strategy digest, the seven stopping rules, the run-directory layout, the durable split, and the
  operator-choice fan-out note.

## Learn more

`ce-optimize` is grounded in Karpathy-style autoresearch discipline: **write results to disk after every
single experiment** so a long run survives context compaction, crashes, and restarts. The
**agent-usability** metric class — token count, steps-to-success, retry rate, plan-readability for an AI
consumer — is an **infiquetra addition**, not present in the source engine.
