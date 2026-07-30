---
title: enhancement(saga): U2 re-key teardown dispositions on worktree path, drop the broker
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

# enhancement(saga): U2 re-key teardown dispositions on worktree path, drop the broker

### Objective
Strip the fleet lease broker out of saga's non-skippable teardown contract in
`plugins/saga/scripts/team_teardown.py`, while preserving the disposition vocabulary teardown's
evidence refs are built from.

Unit **U2** of seven under parent issue #677 (retire the fleet lease broker). Plan:
`docs/plans/2026-07-30-issue-677-lease-broker-retirement-plan.md`. Board objective:
`defects-claude-plugins`.

### Intent
This unit does **not** need to preserve worktree reclamation, because teardown never performed any.
All three production call sites construct `production_adapters(broker)` with no `worktree_reaper`, so
the sweep's reap branch is unreachable in production and every worktree is already left `retained`.
What must survive is the **disposition reporting**, not a removal capability that was never wired.

The file has **13 broker-touching sites**: 11 direct broker-method calls at `:532`, `:806`, `:931`,
`:1036`, `:1072`, `:1105`, `:1214`, `:1228`, `:1260`, `:1311`, `:1403`, plus 2 invocations of the
`_current_head(broker, …)` helper (defined `:1063`) at `:1253` and `:1270`. The methods are `inspect`
×2, `close_owner_admission` ×2, `inspect_owner_admission`, `release` ×4, `sweep(worktree_reaper=…)`,
and `acquire_agent`.

Most are straightforward removals. The `_worktree_sweep` closure at `:1251-1277` is not — it is
lease-indexed end to end:

```python
head, _token = _current_head(broker, lease)                 # :1253  lease head
swept = broker.sweep(worktree_reaper=worktree_reaper)       # :1260  broker enumerates
if lease_id in result.get("reaped_worktree_leases", []):    # :1262  keyed by lease_id
retained_reason = result.get("retained", {}).get(lease_id)  # :1267  keyed by lease_id
follow_up, _ = _current_head(broker, lease)                 # :1270  second lease-head read
```

So this is a **re-key, not a replace**: enumerate worktrees from `git worktree list` cross-referenced
with `outcome_worktrees.py`'s per-leaf routing, and re-key the `ActionOutcome` dispositions
(`already-absent`, `released`, `retained`) on worktree path instead of `lease_id`.

Work from requirement **R5c** in the plan, which carries the full five-outcome disposition inventory.
Do not work from the excerpt above — the closure runs to `:1277`, and an earlier draft that cut it at
`:1272` silently dropped two branches (`released-by-sweep` at `:1272` and the `not-a-sweep-candidate`
fallthrough at `:1277`).

Two consequences from R5c that must land in the replacement: all three evidence-ref strings are
lease-id-namespaced, so they are **redefined, not merely re-keyed**; and `already-absent` **changes
meaning** from "lease head is gone" to "git no longer lists this worktree".

### Out-of-scope / non-goals
- **This unit removes nothing from disk.** It enumerates in order to *report*. Adding worktree
  removal here re-opens KTD8 in full: the broker's `sweep` reaps only when a lease is TTL-expired
  **and** `_owner_state(lease) == "dead"` (`lease_broker.py:4264`, `:4277-4280`), and `git worktree
  list` cannot supply owner-liveness.
- Do not add a direct `git worktree remove`. Issue **#358's R6** — quoted in
  `make_worktree_sweep_adapter`'s docstring, and *not* this plan's R6 — forbids it.
- Do not touch `outcome_compat.py` (U1), `engine_dispatch.py` (U3), or the light consumers (U4).
- No plugin version bump in this unit. Release surfaces move in U7.

### Files expected to change
- `plugins/saga/scripts/team_teardown.py` (1,741 lines; 13 broker-touching sites)
- `tests/test_team_teardown.py`

Agent-facing documentation moves in the same pull request as the behavior it describes (plan
requirement R11). This unit owns the two teardown documents:

- `plugins/team-execution/skills/team-execution/references/teardown-reclamation.md` — directly
  contradicted by the finding that teardown never reclaimed anything
- `plugins/saga/references/teardown-consumer-sites.md` — an inventory of exactly what is being removed

These are executable instruction for agents, not commentary. A skill or reference that tells an agent
to run a lease preflight after the preflight is deleted produces wrong runtime behavior. Do not defer
them to a documentation-only pull request at the end — that guarantees a window where the shipped
skills lie.

Line references were measured at revision `ddba53a0`. Re-grep before editing.

### Tests to add or update
`tests/test_team_teardown.py` — the existing tests assert on lease-keyed dispositions, so they must be
rewritten alongside the code and cannot serve as this unit's safety net. That is why this unit lands
alone rather than batched.

- With no broker present, teardown reports a worktree that `git worktree list` still shows as
  `retained`, with a reason code.
- A worktree git no longer lists yields `already-absent`.
- Teardown with zero worktrees is a clean no-op.
- Teardown of an already-torn-down run is idempotent.
- **Regression sentinel:** teardown removes no worktree from disk under any input. This pins the
  finding that reclamation was never teardown's job.

### Context library links
- Parent issue: https://github.com/Infiquetra/infiquetra-claude-plugins/issues/677
- Plan: `docs/plans/2026-07-30-issue-677-lease-broker-retirement-plan.md` (unit U2, requirement R5c,
  decisions KTD8 and KTD12)
- Document review: `docs/reviews/doc-review-issue-677-2026-07-30.md`
- Origin of the teardown contract being unwound: issue #358 (teardown contract)

### Inputs inventory
- `plugins/saga/scripts/team_teardown.py` at revision `ddba53a0` — the 13 sites listed above.
- The `_worktree_sweep` closure, `:1251-1277`, and its five disposition outcomes as tabulated in the
  plan's requirement R5c.
- `plugins/saga/scripts/outcome_worktrees.py` — per-leaf worktree routing, the enumeration source the
  replacement reads. **This file is concurrently rewritten by U3.**
- `git worktree list` output — the new enumeration source.
- The three production `production_adapters(broker)` call sites, which establish that no
  `worktree_reaper` is ever injected in production.

### Failure modes / pre-mortem
1. **Most likely: U2 and U3 collide through an interface rather than a file.** U2's replacement must
   read `outcome_worktrees.py`'s per-leaf routing, but `team_teardown.py` does **not** import
   `outcome_worktrees` today — verified, zero references in either direction. So U2 must *add* a
   dependency on a module U3 is concurrently rewriting. `assert_no_wave_file_conflicts()` will not
   catch this, because the two units still declare different file sets. **Mitigation: sequence U3
   before U2, or fix the routing interface U2 depends on before either starts.** This sequencing
   choice is an open decision, not settled by the plan.
2. Working from a truncated view of the closure drops the `released-by-sweep` and
   `not-a-sweep-candidate` branches, so those dispositions silently stop being reported. Mitigation:
   work from R5c's table, and assert on all five outcomes in tests.
3. The re-key is mistaken for a rewrite and the disposition vocabulary changes. Downstream evidence
   refs are built from those exact strings. Mitigation: assert the vocabulary explicitly.
4. Someone reads "sweep" and adds removal back. Mitigation: the disk-removal regression sentinel
   above fails loudly.

### Stop conditions
Stop and escalate rather than pressing on if:

- The U2/U3 sequencing question above has not been answered before work starts.
- Reporting a correct disposition turns out to require owner-liveness that `git worktree list` cannot
  supply — that means KTD8's objection has migrated from removal into reporting, and the approach is
  wrong.
- Rewriting `tests/test_team_teardown.py` cannot preserve the existing disposition assertions in a
  re-keyed form, which would mean the vocabulary is not actually portable off `lease_id`.
- The disk-removal regression sentinel fails.

### Acceptance criteria
- [ ] `grep -rn "lease_broker\|lease_authority\|fleet_leases\|_current_head" plugins/saga/scripts/team_teardown.py`
      returns no matches.
- [ ] `uv run pytest tests/test_team_teardown.py -q` passes with all five R5c dispositions asserted.
- [ ] The disk-removal regression sentinel is present and passing: teardown removes no worktree from
      disk under any input.
- [ ] `uv run pytest -q` passes with no failures attributable to this unit.
- [ ] `uv run ruff check . && uv run ruff format --check .` is clean.
- [ ] `uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` is clean.
- [ ] The CHANGELOG records that `already-absent` changed meaning, under a `Changed` heading rather
      than buried under `Removed`.
- [ ] A journal entry ships in the same commit as the code change.

### Verification
```bash
rtk proxy uv run pytest -q                      # baseline BEFORE touching anything
uv run pytest tests/test_team_teardown.py -q
uv run pytest -q
uv run ruff check . && uv run ruff format --check .
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
uv run bandit -r plugins/
python3 scripts/lint_journal_order.py
grep -rn "lease_broker\|lease_authority\|fleet_leases" plugins/saga/scripts/team_teardown.py
```

Cross-unit sentinel:

```bash
uv run pytest tests/test_agy_run_lease.py -q   # must pass UNMODIFIED
```

### Notes / conventions
Land this unit alone, not batched with another. Its own tests are being rewritten in the same change,
so it has no independent safety net.

### Handoff maturity
plan-ready

### Suggested next action
Use `/work <issue>` to execute from the plan-grade context.

### Source context
- Source: `docs/plans/2026-07-30-issue-677-lease-broker-retirement-plan.md` (implementation unit U2)
- Source type: local-file
- Source title: Retire the fleet lease broker — implementation unit U2

### Recommended Tier Band
sonnet/medium

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/679
- Number: 679
- Created at: 2026-07-30T11:37:49.819355+00:00

