---
name: code-review
description: Run a structured Infiquetra code review and pre-PR gate
argument-hint: "[diff, branch, PR, or scope]"
---

Load `saga/skills/code-review/SKILL.md` and run the code-quality review engine at the
work-to-PR boundary: scope the merge-base diff, audit built-vs-planned, run judgment-selected lenses,
validate findings, write a durable `docs/code-reviews/` artifact, and route.

`/code-review` is a **gate, not a fixer**: it reports, classifies, and routes findings — it never
implements the fixes it requests, never mutates reviewed code, never opens or updates a PR, and never
files issues. Its one write lane is its own review artifact: in interactive / standalone mode it may
write, commit, and push that artifact and submit the GitHub pull-request review on an existing PR
(evidence only — the artifact names the exact revision reviewed). Respect the hard boundary in every
mode. When an active work-thread saga exists, it appends
the artifact path to `review_paths` (scan-first, never mint, never advance `lifecycle_phase`) and never
`git add`s the tick.

Arguments provided to the command:

`$ARGUMENTS`
