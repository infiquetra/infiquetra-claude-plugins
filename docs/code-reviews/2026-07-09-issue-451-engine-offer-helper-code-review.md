# Issue #451 Engine Offer Helper Code Review

Date: 2026-07-09
Target: branch `work/451-engine-offer-helper`
Base: `origin/main` at `2e679a5b3065ec2279ff76a4b859c70730d7fdcd`
Reviewed revision: `f04f325db85d4fda2d90e43e67d69ebcb850ccbf`
Issue: `infiquetra/infiquetra-claude-plugins#451`
Plan: `docs/plans/2026-07-09-issue-451-engine-offer-helper-plan.md`
Work session: `docs/work-sessions/2026-07-09-issue-451-engine-offer-helper.md`
Reviewer backend: `inline`
Verdict: PASS

## Scope Check

Scope Check: CLEAN

Intent: Add one shared advisory engine-offer helper for Saga lifecycle stages with repo-local
preferences and conservative mechanical defaults.

Delivered: The branch adds `plugins/saga/scripts/engine_offer.py`, coverage for resolution,
preferences, classifier behavior, CLI round-trip, skill-doc drift, and release metadata sync.

## Review Team

- correctness: always-on; checked closed vocabularies, preference validation, classifier precedence,
  and CLI control flow.
- security: always-on; checked local file IO, malformed JSON handling, and absence of engine dispatch
  or credential-bearing behavior.
- testing: always-on; checked requirement coverage and confirmed the broad vocabulary guard failure was
  fixed.
- maintainability/conventions: always-on; checked release surfaces, `.gitignore`, canonical tier
  vocabulary use, and markdown skill call-site consistency.
- agent-native: selected because the diff adds a CLI helper consumed by markdown-driven Saga skills.

## Plan Completion

COMPLETION: 5/5 DONE, 0 PARTIAL, 0 NOT-DONE, 0 CHANGED, 0 UNVERIFIABLE

- U1 DONE: `plugins/saga/scripts/engine_offer.py:144` resolves offers and `plugins/saga/scripts/engine_offer.py:327`
  exposes the CLI facade.
- U2 DONE: `plugins/saga/scripts/engine_offer.py:182` loads preferences, `plugins/saga/scripts/engine_offer.py:224`
  saves preferences atomically, and `tests/test_engine_offer.py:116` covers repeated save validity.
- U3 DONE: `plugins/saga/scripts/engine_offer.py:119` classifies unit shape, `tests/test_engine_offer.py:179`
  covers mechanical defaulting, and `tests/test_engine_offer.py:192` covers judgment override.
- U4 DONE: the five target skills call `engine_offer.py offer --stage ...` at
  `plugins/saga/skills/ideate/SKILL.md:44`, `plugins/saga/skills/brainstorm/SKILL.md:55`,
  `plugins/saga/skills/work/SKILL.md:78`, `plugins/saga/skills/doc-review/SKILL.md:124`, and
  `plugins/saga/skills/code-review/SKILL.md:75`; `tests/test_engine_offer.py:203` drift-guards them.
- U5 DONE: Saga metadata is bumped at `plugins/saga/.claude-plugin/plugin.json:3`,
  `.claude-plugin/marketplace.json:86`, `plugins/saga/CHANGELOG.md:3`, and
  `tests/test_saga_plugin.py:48`.

## Findings

No P0, P1, P2, or P3 findings.

## Validation Notes

- The first broad pytest run exposed `tests/test_tier_vocab_single_source.py::test_no_bare_model_literals_outside_module`
  because `engine_offer.py` initially re-declared model/effort tuples. The fix now loads
  `tier_palette` via `fleet_commons_shim` at `plugins/saga/scripts/engine_offer.py:18`, and the focused
  single-source vocabulary guard passes.
- The helper has no dispatch or gate-writing path: its public surface is resolution plus local
  preference persistence, and the stage skill snippets explicitly keep the offer advisory-only.

## Coverage

Suppressed findings: 0

Residual risks:

- Prompt ergonomics are documented in the five skill files but will only be proven when each stage is
  exercised in a live operator interaction.

Testing gaps:

- No remaining blocker. Full repo pytest passed with the same Redis-channel exclusions used in this
  outcome's previous leaf.

## Checks Reviewed

- `uv run pytest tests/test_engine_offer.py tests/test_saga_plugin.py tests/test_tier_resolver.py tests/test_saga_engine_resolver.py tests/test_chaperone_economics.py -q`
- `uv run pytest tests/test_engine_offer.py tests/test_tier_vocab_single_source.py::test_no_bare_model_literals_outside_module tests/test_saga_plugin.py::test_infiquetra_lifecycle_metadata_and_marketplace_entry_match -q`
- `COVERAGE_FILE=/tmp/cov-451-full uv run pytest -q --ignore=tests/test_redis_channel_channel.py --ignore=tests/test_redis_channel_notifier.py`
- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports`
- `uv run bandit plugins/saga/scripts/engine_offer.py`
- `uv run python scripts/check_release_surface_parity.py`
- `uv run python scripts/sync_marketplace.py --check`
- `uv run python marketplace/validator/validate.py`
- `python3 tools/release_surface_diff_guard.py --base-ref origin/main`
- `git diff --check`

## Route

PR-ready. Open PR, monitor CI, and merge if checks stay green.
