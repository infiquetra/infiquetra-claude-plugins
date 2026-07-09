# Objective Execution Loop

Use this when an `infiquetra-claude-plugins` objective or outcome-backed campaign resumes and the
next action should not depend on finding an old chat session.

## Canonical Loop

For each active leaf in the outcome frontier:

1. Reconcile the outcome first: `python3 plugins/saga/scripts/outcome.py status <outcome-id>` and
   `python3 plugins/saga/scripts/outcome.py report <outcome-id>`.
2. Route the leaf through `/loop`; if the issue is `requirements-ready`, run `/plan <issue>`.
3. Run `/doc-review` on the plan and fix all P0/P1 findings before work.
4. Run `/work` from the reviewed plan.
5. Run `/code-review` at the work-to-PR boundary and resolve any P0/P1 findings.
6. Push, open the PR, monitor CI, merge when checks are green, and verify the linked issue/PR state.
7. Record the PR on the outcome: `python3 plugins/saga/scripts/outcome.py link-pr <outcome-id> <subplot-id> <pr-url>`.
8. Advance and refresh the outcome: `python3 plugins/saga/scripts/outcome.py advance <outcome-id> --autonomous` and `python3 plugins/saga/scripts/outcome.py report <outcome-id>`.
9. Commit and push the outcome report update before moving to the next frontier leaf.

## Current Campaign

Objective `#336` / outcome `external-engine-offload` uses this loop. The durable source of truth is
the outcome spec/report, GitHub issue and PR state, and committed planning/review/work-session
artifacts. Memory may point here, but memory is not the canonical workflow.

When the outcome frontier returns a `requirements-ready` issue, do not jump straight to code. The
expected sequence is:

```text
/plan -> /doc-review -> /work -> /code-review -> PR -> CI -> merge -> issue close -> outcome advance
```

Use direct GitHub and repo reads at every resume. Old session summaries can help with orientation, but
they must not override current `origin/main`, issue state, PR state, CI status, or the outcome report.
