# Work session — /outcome attend issue-backed handoff (#491)

**Date:** 2026-07-06 · **Issue:** infiquetra/infiquetra-claude-plugins#491 · **Branch:** `feat/491-attend-issue-backed-handoff`
**Plan:** `docs/plans/2026-07-06-outcome-attend-issue-backed-handoff-plan.md` · **Doc-review:** `docs/reviews/2026-07-06-outcome-attend-issue-backed-handoff-doc-review.md`
**Backend:** inline · **Destination:** merge

## What was built (by U-ID)

- **U1 — issue-backed handoff resolver + `attend` fix** (`outcome.py`). `_leaf_handoff_id(node, leaf_saga_id)`
  returns `issue-<N>` when the node is issue-backed (prefer bare `github.sub_issue`, else parse
  `owner/repo#N` from `github.issue` via `outcome_github._parse_ref`), else the raw id. `attend` now
  `load_spec` + `node_by_id` and routes through the resolver. Tests in `test_outcome_command.py`
  (resolver unit tests + `attend` end-to-end: sub_issue, owner/repo#N, no-issue fallback, not-dispatched).
- **U2 — release surface + journal.** saga `plugin.json` 0.71.0→0.72.0; CHANGELOG; `test_saga_plugin.py`
  pin; marketplace synced (9 entries, valid JSON); DECISIONS `{#outcome-attend-issue-backed-handoff-491}`.

## Key decisions

- Reuse #495's `_parse_ref`; inline `f"issue-{N}"` (mirror `derive_saga_id`) rather than import the heavy
  `saga` module. Scope is `attend` only — `outcome_report.py` never emitted the handoff.

## Files modified

`plugins/saga/scripts/outcome.py`, `tests/test_outcome_command.py`,
`plugins/saga/.claude-plugin/plugin.json`, `plugins/saga/CHANGELOG.md`, `tests/test_saga_plugin.py`,
`.claude-plugin/marketplace.json`, `docs/engineering-journal/DECISIONS.md`.

## Checks run

Full command suite (34) green; 8 attend/handoff tests green; ruff check + format clean. Release-surface
diff guard + full suite to be confirmed at the PR gate.

## Next step

Adversarial `/code-review` gate → PR → squash-merge on green → then the #343 capstone (close #343 + board
Done against the derived-truthful 9/9 state, keeping R17).
