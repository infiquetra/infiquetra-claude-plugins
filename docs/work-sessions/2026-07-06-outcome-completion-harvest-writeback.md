# Work session — /outcome completion harvest writeback (#495)

**Date:** 2026-07-06 · **Issue:** infiquetra/infiquetra-claude-plugins#495 · **Branch:** `feat/495-outcome-harvest-writeback`
**Plan:** `docs/plans/2026-07-06-outcome-completion-harvest-writeback-plan.md` · **Doc-review:** `docs/reviews/2026-07-06-outcome-completion-harvest-writeback-doc-review.md`
**Backend:** inline · **Destination:** merge

## What was built (by U-ID)

- **U1 — gh-consumable ref normalization** (`outcome_github.py`). `_parse_ref(ref) -> (owner, repo, number)`
  from `owner/repo#N` or a full URL; `_gh_ref(ref, kind)` emits a gh-consumable token. Wired
  `pr_state`, `issue_state`, `board_status`, `issue_close_info`; routed `_closed_by` through `_parse_ref`
  so a URL doesn't starve its REST events path (the doc-review coupling guard).
- **U2 — `/outcome link-pr <id> <subplot> <pr-url>`** (`outcome.py`). The attended producer that writes
  `node.github["pr"]` — validated (PR URL, code node), idempotent, `save_spec` local + optional `--push`.
  Subparser + dispatch wired beside `prune`/`promote`.
- **U3 — end-to-end harvest-loop integration** (`test_outcome_integration.py`). Proves no-pr→no-harvest,
  `link-pr` merged→harvest→`done`+`complete`, and `owner/repo#N` issue resolves post-normalization.
  Replaces the doc-review-cut vacuous merge-time writeback.
- **U4 — `code:pr-merged` regression guard** (`test_outcome_completion.py`). A closed tracking issue never
  satisfies a code leaf; only a merged `github.pr` does.
- **U5 — release surface + journal.** saga `plugin.json` 0.70.0→0.71.0; CHANGELOG; `test_saga_plugin.py`
  pin; marketplace synced (9 entries); DECISIONS `{#outcome-completion-harvest-writeback-495}`.

## Key decisions

- The fix supplies the **one missing producer** (`link-pr`) that both consumers (harvester barrier +
  auto-merge queue) wait on — it does not touch the correct `code:pr-merged` predicate.
- **R17 preserved** — no derived state persisted into the committed spec JSON.
- The zero-touch autonomous producer is **deferred** (operator-confirmed): `link-pr` is the automation for
  the attended path, which is the only path exercised.

## Files modified

`plugins/saga/scripts/outcome_github.py`, `plugins/saga/scripts/outcome.py`,
`tests/test_outcome_completion.py`, `tests/test_outcome_command.py`, `tests/test_outcome_integration.py`,
`plugins/saga/.claude-plugin/plugin.json`, `plugins/saga/CHANGELOG.md`, `tests/test_saga_plugin.py`,
`.claude-plugin/marketplace.json`, `docs/engineering-journal/DECISIONS.md`.

## Checks run

Full outcome suite (124) green; new U1–U4 tests green; `ruff check` + `ruff format --check` clean;
`mypy plugins/ scripts/ tests/` → "no issues in 149 source files". Release-surface diff guard + full
suite to be confirmed at the PR gate.

## Next step

Run the adversarial `/code-review` gate at the work→PR boundary; open PR; squash-merge on green.
