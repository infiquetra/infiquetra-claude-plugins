# team-execution v2.0.0 Validator Port

## Goal

Port `team-execution` from reviewer-only orchestration to reviewer, validator, and
nonprod automation guidance for Infiquetra repositories.

## Scope

- Bump plugin and marketplace metadata to `2.0.0`.
- Add validator roster, references, agent prompts, and execution rules.
- Add appsec audit skill for URL and input trust-boundary review.
- Reconcile `/team-setup` references with real bundled assets.
- Preserve current base reviewers, including `architecture-reviewer`.
- Remove source-provenance wording and source-domain identifiers from plugin files.

## Phases

1. Baseline inspect current plugin, tests, manifests, setup assets, and journal.
2. Add targeted failing tests for the v2 contract.
3. Update plugin docs, commands, references, agents, skills, assets, and metadata.
4. Run targeted plugin tests, metadata/link/forbidden-term checks, and supported repo checks.
5. Update engineering journal and commit scoped changes.

## Current State

- Branch: `feat/team-execution-v2-validator-port`
- Metadata, docs, references, validator agents, appsec skill, and setup assets updated.
- Engineering journal entries added for setup asset drift and validator orchestration decision.
- Tracked source-domain residue removed from scaffold templates, examples, changelogs, and tests.

## Checks Run

- `git status --short`
- Team-execution file inventory and content inspection
- `uv run pytest tests/test_team_execution_plugin.py -q` (red, then green)
- `uv run ruff check .`
- `uv run pytest` (553 passed)
- `uv run bandit -r plugins/team-execution`
- `uv run bandit -r plugins/` (fails on pre-existing low-severity findings outside this change)
- `git diff --check`
- transient tracked-file forbidden-term scan
