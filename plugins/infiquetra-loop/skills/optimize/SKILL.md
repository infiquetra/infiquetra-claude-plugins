---
name: optimize
description: Metric-driven Infiquetra optimization loop for measurable performance, cost, reliability, or workflow improvements.
---

# Optimize

Use this when success is measurable and iteration should be bounded.

## Workflow

1. Define the metric and acceptable measurement method.
2. Capture a baseline before changing behavior.
3. Pick a small experiment set and expected impact.
4. Change one meaningful variable at a time when possible.
5. Record results, checks, and tradeoffs under `docs/qa/` or a plan-linked notes file.
6. Stop when the target is reached, the experiment fails, or the next step needs a strategy
   decision.

Raw benchmark output and temporary profiles belong under `.claude/infiquetra-loop/`.
