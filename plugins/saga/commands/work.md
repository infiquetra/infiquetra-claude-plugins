---
name: work
description: Execute an approved Infiquetra plan to PR-ready, then own the round-N PR continuation loop with saga state, risk-gated tests, a hard review gate, and merge under explicit confirmation
argument-hint: "[plan path or issue]"
---

Load `saga/skills/work/SKILL.md`. Execute from a durable plan artifact or a handoff issue
marked `plan-ready` or `resume-ready`.

`/work` is the saga's **primary writer**: it restores on resume, mints/advances the work-thread saga to
`lifecycle_phase=work`, writes a tick per phase, and names that saga identity into the programmatic
`/code-review` call so the review's `review_paths` append lands on the exact thread.

It executes to the **PR-ready boundary**, then owns the **round-N PR continuation loop** (re-reads live PR
state and runs the transition table on re-entry). It gates **hard** on unresolved P0/P1 findings or a
stale review, and applies risk-based test gates (`requires_hard_test_gate`).

Merge is a git op `/work` owns, but **only under explicit operator confirmation** — never silent. `/work`
does **not** own deploy or canary (`deploy`), does **not** file SDLC issues (`mission-control`),
and does **not** advance `lifecycle_phase` past `work` (the `qa` advance is deferred to the `/qa`
rebuild). Update issue progress through `mission-control`, write `docs/work-sessions/` summaries, and do not
close or move the issue until acceptance criteria and the selected destination are satisfied.

Arguments provided to the command:

`$ARGUMENTS`
