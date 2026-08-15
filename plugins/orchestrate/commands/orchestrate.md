---
name: orchestrate
description: Orchestrate a whole outcome across Claude, Codex, and other vendor children from one invocation — an issue, a parent issue, a requirements doc, or a prose prompt, with no decomposition required up front. Discovers the work's shape during planning, then dispatches, tracks, and completes vendor children through a durable register without an operator turn between steps.
argument-hint: "[issue number | parent issue | requirements doc | prose prompt]"
---

Load `orchestrate/skills/orchestrate/SKILL.md` and orchestrate the given outcome.

`/orchestrate` takes the outcome as its **argument**, not as something that must already be shaped
into a graph before invocation — the work's structure is discovered during planning instead of
decomposed up front. It dispatches children across Claude, Codex, and other vendors, tracks each one
in a durable per-run register, wakes on the child's own events rather than polling for status, and
completes a child only once a bounded predicate passes on a settled, run-bound artifact. It does not
run a child's work in-context: leaf work stays native to whichever vendor and surface that child was
dispatched to.

Arguments provided to the command:

`$ARGUMENTS`
