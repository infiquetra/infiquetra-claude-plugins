---
issue: infiquetra/infiquetra-claude-plugins#325
plan: docs/plans/2026-07-03-readonly-verifier-registration-fallback-plan.md
branch: fix/325-readonly-verifier-fallback
status: PR-ready
---

# readonly-verifier roster gap — fallback ladder + drift guard

## What was built

- **U1** — `plugins/saga/references/sandbox-spawn-sites.md` gained a "Fallback when
  `saga:readonly-verifier` is unavailable" section: a two-step ladder (`Explore` + worktree first,
  `general-purpose` + worktree + prose instruction only if `Explore` is also absent).
  `CLAUDE.md`'s ad-hoc spawn rule now points to it. Commit `09e1ba3`.
- **U2** — `tests/test_agent_registration_drift.py` (new): 10 tests pinning static
  discoverability — frontmatter `name:` matches file stem, `execution_spec.py`'s
  `READONLY_VERIFIER_AGENT_TYPE` matches the on-disk agent, spawn-context (`subagent_type`/
  `agentType`) `saga:<name>` references resolve, the fallback section is documented — plus 3
  synthetic-negative regression cases proving each assertion isn't vacuous. Commit `5a98909`.
- **U3** — saga `plugin.json` / `marketplace.json` bumped 0.49.1 → 0.49.2, `CHANGELOG.md` entry,
  `LEARNINGS.md` `{#stale-agent-roster-325}`, `DECISIONS.md`
  `{#readonly-verifier-fallback-ladder-325}`. Also updated the pre-existing version-drift-guard
  literal in `tests/test_saga_plugin.py:48` (found during the release-surface pass — CI pins this
  string and would have failed on the bump otherwise). Commit `307f0d2`.

## Key decisions

- **Key Technical Decision 1** — fallback is `Explore`-first, not `general-purpose`-only: `Explore`
  structurally omits `Edit`/`Write` while keeping `Bash`, preserving the read-only axis by tool
  omission rather than by prompt request.
- **Key Technical Decision 2** — the drift guard asserts static discoverability, not runtime
  registration (the actual #325 failure mode — a stale session roster — is unobservable from CI).
- Full rationale in `docs/plans/2026-07-03-readonly-verifier-registration-fallback-plan.md` and
  `docs/engineering-journal/DECISIONS.md#readonly-verifier-fallback-ladder-325`.

## Files modified

- `plugins/saga/references/sandbox-spawn-sites.md`
- `CLAUDE.md`
- `tests/test_agent_registration_drift.py` (new)
- `plugins/saga/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `plugins/saga/CHANGELOG.md`
- `docs/engineering-journal/LEARNINGS.md`
- `docs/engineering-journal/DECISIONS.md`
- `tests/test_saga_plugin.py`

## Checks run

- `uv run pytest -q` — 1821 passed
- `uv run ruff check .` — all checks passed
- `uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` — no issues, 117 source files
- JSON validity check on both bumped registries

## Issue-#325 proposed-fix disposition

1. "Verify the reload path" — answered at plan time, not by code: a live `saga:readonly-verifier`
   spawn in a fresh session resolved and ran successfully, confirming stale-roster root cause.
   Recorded as evidence in the plan and in `LEARNINGS.md`.
2. "Add a documented fallback" — shipped as U1.
3. "Add a drift-guard test" — shipped as U2, scoped to static discoverability (see Key Technical
   Decision 2 for why runtime registration can't be guarded from CI).

## Next step

Run the code-review gate, then offer PR-open against `main`.
