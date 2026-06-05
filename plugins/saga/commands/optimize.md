---
name: optimize
description: Run a metric-driven Infiquetra optimization loop
argument-hint: "[metric, workflow, or bottleneck]"
---

Load `saga/skills/optimize/SKILL.md` and run the metric-driven optimization engine.

The spine: define a measurable spec (primary metric + direction + scope + at least one degenerate gate),
baseline current behavior, generate a hypothesis backlog, then run **bounded one-variable experiments** —
measure, run hard degenerate gates BEFORE any LLM-judge, keep the best real improvement and revert the
rest, write a strategy digest between batches, and converge under the stopping rules. The eight metric
classes: perf, cost, reliability, agent-usability, security, quality/accuracy, developer-experience,
maintainability.

`/optimize` is **off-chain and saga-untouched** — it writes no saga and never advances a lifecycle phase.
The default loop is serial and in working state; for independent experiment fan-out it **offers** an
execution backend (operator-choice) and records the choice narratively. It finds the measurably-best
version, then **routes the winning change to /work to ship** — it never runs `gh issue create`
(`mission-control` owns issue bodies) and never auto-merges an experiment.

Treat `$ARGUMENTS` as the optimization goal — a metric, a workflow, or a named bottleneck.

`$ARGUMENTS`
