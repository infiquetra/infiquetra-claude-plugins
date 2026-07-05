---
title: Work session — ship_ceremony.py primitive (#345)
type: work-session
status: complete
date: 2026-07-04
---

# Work session — ship_ceremony.py primitive (#345)

**Issue:** infiquetra/infiquetra-claude-plugins#345 (pf-ship-ceremony-primitive)
**Plan:** `docs/plans/2026-07-04-ship-ceremony-primitive-plan.md`
**Doc review:** `docs/reviews/2026-07-04-ship-ceremony-primitive-345-doc-review.md` (clean, 2 safe fixes applied pre-work)
**Branch:** `feat/pf-ship-ceremony-345`
**Backend:** inline (Gate E draft recommended team-execution; operator chose inline — same pattern as #461/#399/#463)

## Units shipped

- **U1** — Transition-table core (`plugins/saga/scripts/ship_ceremony.py`): ordered
  `TRANSITIONS` tuple, local `CeremonyTier` registry (KTD1), `next_transition()`
  index derivation (no stored index — KTD2), `resolve_saga()` filtering `saga.py
  scan`'s output by branch with ambiguity refusal.
- **U2** — `saga.py` schema (`--ceremony-transition` / `--ceremony-tier`, new
  `CEREMONY_TIERS` constant, `saga-spec.md` documentation) — ceremony state rides
  the existing work-thread saga tick, verified via a real save/restore/carry-forward
  round-trip before wiring the rest of the primitive against it.
- **U3** — `work/SKILL.md` section 5.4 and `references/pr-continuation-loop.md`
  rewired to name `ship_ceremony.py` as the mechanism for PR-open/review-request/
  merge/cleanup, preserving the exact operator-confirmation language (R5). AC6 grep
  verified clean.
- **U4** — Git-surface entry point: `ship_ceremony.py install`/`uninstall` (local,
  repo-scoped `git ship` alias; force-guard against clobbering an unrelated existing
  alias — a gap doc-review caught in the plan and this session verified is actually
  guarded in code).
- **U5** — Front-loaded `ship_ceremony.py start` mode, offered right after `/work`
  Phase 1.4's saga mint; records `pr_refs` immediately; the later `open_pr`
  transition detects it and flips the draft ready instead of opening a second PR.
- **U6** — Release surfaces: saga `0.53.0` → `0.54.0` (plugin.json, marketplace.json,
  CHANGELOG), drift-guard version string in `tests/test_saga_plugin.py`, execution-order
  checklist row 4 ticked, DECISIONS entry `{#ship-ceremony-primitive-345}`.

## Implementation notes (deviations from the plan, evidence-backed)

- The plan's KTD2 described a nested `ceremony_state` block; the saga tick format only
  supports flat scalar/list fields, so U2 implements two flat scalars
  (`ceremony_transition`, `ceremony_tier`) instead — same intent, format-compatible.
  `saga.py` deliberately does not import `ship_ceremony.py`'s `TRANSITIONS` ordering;
  `CEREMONY_TIERS` is its own small closed-vocabulary constant, keeping the generic
  saga engine decoupled from one consumer's transition table.
- `_do_open_pr` needed to record `pr_refs` itself when creating a genuinely new PR
  (not just on the `start`-then-flip-ready path) — caught by the full-ceremony test
  failing on `request_review`'s "no pr_refs recorded" check, fixed before the gate ran.

## Test design

`tests/test_ship_ceremony.py` (23 tests): pure-logic tests for `next_transition` /
tier declarations; a real throwaway git repo + real local bare "origin" for every
git-only transition and the alias install/uninstall (no network, and the module is
registered in `tests/conftest.py`'s `_GH_WRITE_TEST_MODULES` #279 hard floor as
defense in depth); a `FakeGh` for PR-facing transitions that pushes the branch's
commit to the bare origin's `main` on a faked merge, so the downstream real
`checkout_main`/`pull` transitions observe a genuinely changed repo rather than a
no-op. Covers all seven ACs (AC1–AC7) named in the issue.

## Checks run

- `uv run pytest -q` — 1951 passed (repo-wide; 23 new for `ship_ceremony.py`).
- `uv run ruff format --check .` — clean.
- `uv run ruff check .` (targeted + full) — clean.
- `uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` — clean (fixed one
  `no-any-return` finding in a test helper before this passed).
- `uv run bandit -r plugins/saga/scripts/ship_ceremony.py` — no issues; repo-wide
  bandit shows only pre-existing findings in unrelated files.
- `grep -nE "git (checkout|pull|branch -d)|gh pr (create|merge)" plugins/saga/skills/work/SKILL.md` — no matches (AC6).

## Notes

`.serena/project.yml` is a pre-existing unrelated local modification, excluded from
this PR's commit per the program's standing convention.
