---
title: enhancement(saga): U3 unwind lease from dispatch and per-leaf worktree routing
repo: infiquetra-claude-plugins
type: enhancement
team: campps
project: operations
status: Idea
labels: enhancement, hermes-task, needs-plan
risk: high
handoff_maturity: plan-ready
approval_state: needs_operator_approval
---

# enhancement(saga): U3 unwind lease from dispatch and per-leaf worktree routing

### Objective
Remove the fleet lease broker from saga's engine dispatch and per-leaf worktree routing —
`plugins/saga/scripts/engine_dispatch.py` and `plugins/saga/scripts/outcome_worktrees.py` — and ship a
documented operator-facing reclamation path to replace the one automatic worktree reaper that
actually runs in production.

Unit **U3** of seven under parent issue #677 (retire the fleet lease broker). This is the largest unit
by call-site count and the one where the real reclamation loss lands. Plan:
`docs/plans/2026-07-30-issue-677-lease-broker-retirement-plan.md`. Board objective:
`defects-claude-plugins`.

### Intent
These are the two files where broker use is genuinely threaded through the logic rather than
localized: `engine_dispatch.py` (2,586 lines, ~23 sites; loads at `:799`, `:1043`, `:1960`, `:2453`)
and `outcome_worktrees.py` (980 lines, ~16 sites; imports at `:47`).

**The loader looks degradation-tolerant and is not.** `engine_dispatch.py:800-804` converts a graceful
`None` into a raised `DispatchError`, and `_require_lease_protocol()` at `:805` additionally pins
`_REQUIRED_LEASE_PROTOCOL_VERSION`. There is no existing no-lease path to fall back into. Each of the
four load sites needs its hard requirement and its version gate removed, plus whatever
`lease_admission.validate()` and `_bounded_lease_identity()` feed at `:796-798`. Check whether
`_require_lease_protocol` and `_REQUIRED_LEASE_PROTOCOL_VERSION` have any non-lease callers before
deleting them.

**One easy-to-miss dependency:** `outcome_worktrees.py` takes a `lease_ttl_seconds` parameter at
`:384`, `:572`, and `:838`, each **defaulting to the broker constant**
`fleet_leases.authority.DEFAULT_TTL_SECONDS`. That default vanishes with the module, so each signature
needs either a literal replacement default or the parameter removed — and
`tests/test_outcome_worktrees.py` passes `lease_ttl_seconds=` explicitly at ten call sites, so the
choice is test-visible. **This is a different `lease_ttl_seconds` from the liveness observation field
renamed in U6. Do not conflate them.**

**This unit is where the one real reclamation loss lands.** `outcome_worktrees.py:674` is the *only*
production site that actually reaps: `swept = lease_authority.sweep(worktree_reaper=_validated_reaper)`.
Deleting it means stale per-leaf outcome worktrees accumulate until reclaimed by hand. Two obligations
follow, neither optional:

1. The decision record must name this loss specifically — **outcome** worktrees, not "worktrees".
2. This unit ships an operator-facing reclamation path to replace it, even a manual one: a documented
   `git worktree list` plus prune procedure, or a small script. Deleting an automatic reaper and
   leaving no documented substitute converts an accepted loss into an unrecorded one.

Finally, handle admission's third capability here. `engine_dispatch.py:796-798` feeds
`lease_admission.validate()` and `_bounded_lease_identity()`. The identity check becomes
caller-asserted — the one accepted loss taken on judgment rather than measurement. Note that in the
code comment that replaces the check, so the next reader knows it was a decision and not an oversight.

### Out-of-scope / non-goals
- Do not touch `outcome_compat.py` (U1), `team_teardown.py` (U2), or the four light consumers (U4).
- Do not delete any `fleet_commons` module — that is U7.
- Do not build an automatic replacement reaper. The accepted substitute is a documented manual
  reclamation path; building an automatic one is a scope reversal and needs its own decision.
- Do not treat the two concurrent dispatches of the same leaf now both proceeding as a bug to fix.
  Losing dispatch idempotency is an accepted loss, pinned as intended behavior by a test below.
- No plugin version bump in this unit. Release surfaces move in U7.

### Files expected to change
- `plugins/saga/scripts/engine_dispatch.py` (2,586 lines, ~23 sites)
- `plugins/saga/scripts/outcome_worktrees.py` (980 lines, ~16 sites)
- `tests/test_engine_dispatch.py`
- `tests/test_outcome_worktrees.py`
- New or updated operator documentation for the manual worktree reclamation path
- `docs/engineering-journal/DECISIONS.md` — the reclamation-loss record

Agent-facing documentation moves in the same pull request as the behavior it describes (plan
requirement R11). This unit owns:

- `plugins/saga/skills/work/SKILL.md` — 8 lease references spanning dispatch and teardown; assigned
  here because this unit removes the dispatch behavior it leans on hardest. It is the most-used
  surface in the repository, and it is executable instruction for agents rather than commentary.

Line references were measured at revision `ddba53a0`. Re-grep before editing.

### Tests to add or update
`tests/test_engine_dispatch.py`:

- Dispatch completes with no lease module importable.
- A dispatch that previously acquired a lease still records its engine resolution.
- Two concurrent dispatches of the same leaf both proceed and neither raises — this pins the accepted
  idempotency loss as intended behavior rather than letting it read as a regression later.

`tests/test_outcome_worktrees.py`:

- A sub-outcome routes into its own worktree with no lease.
- Two sub-outcomes get distinct worktrees.
- Worktree cleanup runs without lease release.
- The documented manual reclamation path removes a stale leaf worktree.
- The ten existing `lease_ttl_seconds=` call sites reflect whichever signature choice was made.

### Context library links
- Parent issue: https://github.com/Infiquetra/infiquetra-claude-plugins/issues/677
- Plan: `docs/plans/2026-07-30-issue-677-lease-broker-retirement-plan.md` (unit U3, decisions KTD9 and
  KTD12, Scope Decision rows 2 and 3)
- Document review: `docs/reviews/doc-review-issue-677-2026-07-30.md`
- The analysis that made per-leaf worktrees the redundancy argument: issue #671

### Inputs inventory
- `engine_dispatch.py` at `ddba53a0`: the four load sites `:799`, `:1043`, `:1960`, `:2453`; the
  `DispatchError` conversion at `:800-804`; `_require_lease_protocol()` at `:805`;
  `_REQUIRED_LEASE_PROTOCOL_VERSION`; `lease_admission.validate()` and `_bounded_lease_identity()` at
  `:796-798`.
- `outcome_worktrees.py` at `ddba53a0`: the import at `:47`; the `lease_ttl_seconds` parameter at
  `:384`, `:572`, `:838` with its `fleet_leases.authority.DEFAULT_TTL_SECONDS` default; the sole
  production reaper at `:674`.
- `tests/test_outcome_worktrees.py`: ten explicit `lease_ttl_seconds=` call sites.
- Prior art for the manual path: an earlier manual cleanup in this workspace removed 88 redundant
  worktrees.

### Failure modes / pre-mortem
1. **Most likely: the reclamation loss ships undocumented.** The reaper deletion is one line; the
   operator-facing substitute is real work and is easy to defer past the pull request. Mitigation:
   the acceptance criteria below make the documented path and the named decision record blocking, and
   a test exercises the procedure.
2. **The two `lease_ttl_seconds` are conflated with U6's.** They are unrelated: this one is a worktree
   TTL parameter defaulting to a broker constant, U6's is a serialized liveness-event wire field.
   Conflating them produces either a wrong rename here or a missed rename there. Mitigation: this unit
   touches no file in U6's rename table.
3. The removal assumes a graceful no-lease path exists. It does not — the loader raises. Mitigation:
   all four load sites are enumerated above and each needs explicit handling.
4. `_require_lease_protocol` or `_REQUIRED_LEASE_PROTOCOL_VERSION` turn out to have a non-lease caller
   and get deleted anyway. Mitigation: check callers before deleting, as stated.
5. U2 adds a dependency on this file's routing interface while this unit is rewriting it. See the
   sequencing question on U2 — it is unresolved and must be answered before both start.

### Stop conditions
Stop and escalate rather than pressing on if:

- The U2/U3 sequencing question has not been answered before work starts.
- No workable operator-facing reclamation path can be written — that would convert an accepted loss
  into an unrecorded one, which the plan forbids.
- `_require_lease_protocol` or `_REQUIRED_LEASE_PROTOCOL_VERSION` has a non-lease caller that cannot
  be cleanly separated.
- Removing the identity check turns out to have a consumer that genuinely depends on it, rather than
  it being caller-assertable.

### Acceptance criteria
- [ ] `grep -rn "lease_broker\|lease_authority\|fleet_leases" plugins/saga/scripts/engine_dispatch.py plugins/saga/scripts/outcome_worktrees.py`
      returns no matches.
- [ ] `uv run pytest tests/test_engine_dispatch.py tests/test_outcome_worktrees.py -q` passes,
      including the concurrent-dispatch test that pins the accepted idempotency loss.
- [ ] The operator-facing worktree reclamation procedure is written and is exercised by a test.
- [ ] `docs/engineering-journal/DECISIONS.md` names the loss as **outcome worktrees** specifically,
      with the manual substitute and a revisit-when condition.
- [ ] The code comment replacing the identity check states that caller-asserted identity was a
      decision, not an oversight.
- [ ] `uv run pytest -q` passes with no failures attributable to this unit.
- [ ] `uv run ruff check . && uv run ruff format --check .` is clean.
- [ ] `uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` is clean.

### Verification
```bash
rtk proxy uv run pytest -q                      # baseline BEFORE touching anything
uv run pytest tests/test_engine_dispatch.py tests/test_outcome_worktrees.py -q
uv run pytest -q
uv run ruff check . && uv run ruff format --check .
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
uv run bandit -r plugins/
python3 scripts/lint_journal_order.py
grep -rn "lease_broker\|lease_authority\|fleet_leases" plugins/saga/scripts/engine_dispatch.py plugins/saga/scripts/outcome_worktrees.py
```

Cross-unit sentinel:

```bash
uv run pytest tests/test_agy_run_lease.py -q   # must pass UNMODIFIED
```

### Notes / conventions
`outcome_worktrees.py` is the file that routes sub-outcomes into per-leaf worktrees — the *second*
isolation mechanism, and the reason the broker was redundant for outcome paths in the first place. Its
lease use is mostly bookkeeping over an isolation it already achieves structurally. The reaper at
`:674` is the one exception, and it is why this unit carries the reclamation obligation.

### Handoff maturity
plan-ready

### Suggested next action
Use `/work <issue>` to execute from the plan-grade context.

### Source context
- Source: `docs/plans/2026-07-30-issue-677-lease-broker-retirement-plan.md` (implementation unit U3)
- Source type: local-file
- Source title: Retire the fleet lease broker — implementation unit U3

### Recommended Tier Band
sonnet/medium

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/680
- Number: 680
- Created at: 2026-07-30T11:38:03.359227+00:00

