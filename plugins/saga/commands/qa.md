---
name: qa
description: Run Infiquetra quality, browser, deployment, and acceptance checks
argument-hint: "[scope]"
---

Load `saga/skills/qa/SKILL.md`. Run the **acceptance-evidence GATE** on shipped work:
answer "does the shipped thing actually work?" with risk-driven, evidence-backed checks.

`/qa` is **gate-only** — it restores the work-thread saga, classifies the change into the 9-way risk
router, runs acceptance checks per class (browser behavior via the installed MCP), assigns
critical/high/medium/low severity, derives a `ship` / `ship-with-deferred` / `no-ship` verdict from the
tier threshold, reports a ported deterministic 0-100 health score alongside it (one signal; the banded
verdict is the gate), writes a durable artifact to `docs/qa/`, and routes.

On **PASS** it advances the saga qa-track (`lifecycle_phase` work→qa, writes `qa_paths`) and routes to
`/handoff` or `/retro`. On **FAIL** it keeps `lifecycle_phase=work` and routes by **merge state** —
pre-merge to `/work` (re-enter the round-N loop), post-merge to `/handoff` (open a new defect thread).

`/qa` does **NOT** fix bugs, does **NOT** edit code, does **NOT** commit, does **NOT** push, does
**NOT** open, update, or merge a PR, does **NOT** deploy, does **NOT** file SDLC issues, and does
**NOT** set readiness labels. It reports, verdicts, and routes — then stops.

Arguments provided to the command:

`$ARGUMENTS`
