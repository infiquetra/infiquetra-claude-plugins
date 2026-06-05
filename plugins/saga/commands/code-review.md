---
name: code-review
description: Run a structured Infiquetra code review and pre-PR gate
argument-hint: "[diff, branch, PR, or scope]"
---

Load `saga/skills/code-review/SKILL.md` and run the code-quality review engine at the
work-to-PR boundary: scope the merge-base diff, audit built-vs-planned, run judgment-selected lenses,
validate findings, write a durable `docs/code-reviews/` artifact, and route.

`/code-review` is a **gate, not a fixer**: it reports, classifies, and routes findings — it does not
mutate code, commit, push, open PRs, or file issues. When an active work-thread saga exists, it appends
the artifact path to `review_paths` (scan-first, never mint, never advance `lifecycle_phase`) and never
`git add`s the tick. Respect the hard boundary in every mode.

Arguments provided to the command:

`$ARGUMENTS`
