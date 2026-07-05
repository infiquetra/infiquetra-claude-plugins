---
title: ship_ceremony.py request_review transition — fix invalid `@me` reviewer request
type: fix
status: active
date: 2026-07-04
origin: https://github.com/infiquetra/infiquetra-claude-plugins/issues/477
---

# ship_ceremony.py request_review transition — fix invalid `@me` reviewer request

## Problem

`_do_request_review` (`plugins/saga/scripts/ship_ceremony.py:278-282`) always shells out to
`gh pr edit <N> --add-reviewer @me`. `@me` is not a valid login for the underlying
`requestReviewsByLogin` GraphQL mutation, so this call fails on every real ceremony run — confirmed
against PR #475 (issue #429's `/work` session), where the transition never once succeeded.

Because `run()` (`ship_ceremony.py:346-369`, the same not-advance-on-failure contract every
transition relies on) correctly refuses to advance `ceremony_transition` past a failed call, there
is no state corruption — the ceremony simply stalls at `request_review` forever, on every
invocation, for every future ceremony run. The defect is total and permanent, not intermittent.

## Requirements

**R1.** `request_review` must complete without shelling out to a call that is guaranteed to fail,
for every ceremony run in this repository.

**R2.** The fix must not introduce a second external call that is *also* guaranteed (or likely) to
fail in this repository's actual operating conditions.

**R3.** `ceremony_transition` must still advance past `request_review` to `merge` exactly as it does
for every other transition — no special-cased skip logic in `run()`'s dispatch table.

## Key Technical Decisions

- **KTD1 — make `request_review` a no-op transition, not a resolved-login reviewer request.** The
  issue's own suggested fix offers two paths: (a) resolve the real authenticated login via
  `gh api user -q .login` and use that instead of `@me`, or (b) drop `request_review` as a no-op
  for solo-maintainer repos. This plan takes (b).

  Rationale: this repository has exactly one human maintainer (Jeff), who is also the sole author
  of every ceremony PR. Requesting review from yourself has no one to add value regardless of
  whether the underlying call would technically succeed, so a no-op satisfies R1/R2
  unconditionally on that fact alone. Path (a) — resolving the real login via
  `gh api user -q .login` and requesting it — carries an *additional, unverified* risk this plan
  does not rely on to justify (b): GitHub's reviewer-request path is widely understood to reject a
  self-review request from the PR's own author, which would make path (a) trade one known-fail
  call for a plausibly-still-fail call. That secondary point is offered as context, not as this
  decision's load-bearing evidence — the solo-maintainer fact above is sufficient on its own.

  `_do_request_review` becomes a no-op function body (a docstring explaining why, no `_run` call).
  It stays registered in `_RUNNERS` and `TRANSITIONS` unchanged — R3 requires the transition to
  still exist and still advance state exactly like every other transition; only its *body* changes
  from "shell out to a call that always fails" to "nothing to do."

  *Rejected:* resolving `gh api user -q .login` and requesting that login — adds a second external
  call for zero verified benefit (no second reviewer exists to notify) even setting aside the
  self-review-restriction risk.
  *Rejected:* making the reviewer configurable via a new CLI flag or config key — over-engineered
  for a solo-maintainer repo with no near-term plan to add a second human reviewer; adds a surface
  nothing currently consumes (the dead-wiring pattern this repo's own journal already flags).

## Implementation Units

### U1. Make `_do_request_review` a no-op

**Files:** `plugins/saga/scripts/ship_ceremony.py`

Replace the body of `_do_request_review` (`:278-282`) with a no-op. Keep the function's signature
identical (`saga`, `*, repo_root`, `runner` — even though none of the three are used by a no-op
body, the signature must match every other entry in `_RUNNERS: Mapping[str, Callable[..., None]]`
so the dispatch table in `run()` keeps calling it uniformly). Add a docstring stating why (KTD1:
solo maintainer, no one to request review from) and noting the no-op is deliberate and dated, so a
future reader hitting this function doesn't mistake the empty body for an oversight or file a
duplicate defect against it. The module docstring (`:12-18`) needs no change — its existing framing
("invoked only when the caller ... explicitly asks for the next step") already holds structurally
for a no-op transition.

**Test scenarios** (`tests/test_ship_ceremony.py`):

- `test_request_review_is_a_noop`: call `SC._do_request_review(saga, repo_root=repo, runner=fake_gh_that_raises_on_any_call)` directly and assert it returns without calling the runner at all (a runner that raises `AssertionError` on any `__call__` proves no subprocess call was attempted).
- `test_full_ceremony_throwaway_branch` (existing, `tests/test_ship_ceremony.py:237`): no change needed to the test body, but confirms end-to-end that a full seven-transition ceremony run still completes with `request_review` in the sequence and `FakeGh` never receives a `pr edit --add-reviewer` call (`FakeGh._handle_gh`'s existing `["pr", "edit"]` branch at `:134-135` will simply see zero invocations for this transition going forward — no assertion change required, since it never asserted call count).
- `test_resume_from_state` (existing, `:254`): no change needed — it only asserts `ceremony_transition == "request_review"` after 3 runs, which still holds.

### U2. Bump saga's release surfaces (plugin.json + CHANGELOG.md)

**Files:** `plugins/saga/.claude-plugin/plugin.json`, `plugins/saga/CHANGELOG.md`

`ship_ceremony.py` lives under `plugins/saga/scripts/`, not `tests/` or a doc-exempt path, so
`tools/release_surface_diff_guard.py` (shipped in #429, wired into CI's `release-surfaces` job)
hard-blocks this PR unless both files change alongside U1's code edit. Saga is currently at
`0.54.1` (`plugins/saga/CHANGELOG.md`'s top heading). Bump to `0.54.2` (patch — a defect fix, not a
new feature or breaking change) in both `plugin.json`'s `version` field and a new
`## [0.54.2] - <PR-merge-date>` CHANGELOG heading (canonical grammar per KTD1 in
`docs/plans/2026-07-05-release-surface-single-source-plan.md` — dated heading, no name-suffix
title), describing the `request_review` no-op fix and citing issue #477.

**Test scenarios:** the existing tri-lock parity test suite
(`tests/test_release_surface_parity.py`) and `tests/test_release_surface_diff_guard.py` already
cover this generically — no new test needed, but CI's `release-surfaces` job (`.github/workflows/ci.yml`)
and a local run of `python3 scripts/check_release_surface_parity.py` must both pass before merge.
Also update `.claude-plugin/marketplace.json` via `python3 scripts/sync_marketplace.py` (write mode)
so the marketplace entry's version stays in lock-step (the tri-lock's third leg).

## Scope Boundaries

**Out of scope:**

- Making the reviewer configurable for a hypothetical future second maintainer (KTD1's rejected
  alternative) — revisit only if a second human maintainer actually joins this repo.
- Issue #478 (the separate `open_pr` unpushed-commits defect) — tracked independently, not bundled
  into this fix.
- Any change to `_do_open_pr`, `_do_merge`, or any other transition — this defect and fix are
  scoped to `request_review` alone.

**Deferred follow-up work:** none identified.

## Verification

```bash
uv run pytest tests/test_ship_ceremony.py -v
uv run ruff check plugins/saga/scripts/ship_ceremony.py tests/test_ship_ceremony.py
uv run ruff format --check plugins/saga/scripts/ship_ceremony.py tests/test_ship_ceremony.py
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
python3 scripts/sync_marketplace.py --check
python3 scripts/check_release_surface_parity.py
python3 tools/release_surface_diff_guard.py --base-ref origin/main
```
