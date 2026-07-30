---
title: defect(fleet): worktree-declared reservation claimed without worktree_root yields an unfenced lease
repo: infiquetra-claude-plugins
type: defect
team: asgard
project: operations
status: Shaping
labels: defect, hermes-task, needs-plan
risk: low
handoff_maturity: requirements-ready
approval_state: needs_operator_approval
---

# defect(fleet): worktree-declared reservation claimed without worktree_root yields an unfenced lease

## Problem

A reservation declared `isolation='worktree'` that is later claimed with no `worktree_root`
yields an **unfenced** lease: the claim's fence branch stamps only when a root is available, so
the declared-isolation intent silently degrades to no write fence (fleet-core 0.20.0
`fleet_commons/lease_broker.py:2692` fall-through).

Confirmed **pre-existing** by the #643 code review (finding 2, deferred advisory): the 0.19.0
baseline had the identical fall-through with no isolation gate, and the shipped saga adapter
path cannot reach it (`_canonical_cwd` raises rather than returning None). Risk is confined to
future direct broker callers or alternative adapters.

## Acceptance sketch

- A claim for a `isolation='worktree'` reservation with no resolvable worktree_root fails loud
  (LeaseBrokerError) instead of granting an unfenced lease.
- Regression test pinning the refusal.

## Evidence

- `docs/code-reviews/2026-07-23-issue-616-worktree-write-fence-scoping-code-review.md`
  (finding 2, CONFIRMED / pre-existing)

### Files expected to change

- `plugins/fleet-core/scripts/fleet_commons/lease_broker.py` — claim fence branch (:2691-2700)
- Release surfaces: plugin.json, marketplace.json, CHANGELOG, drift pins

### Tests to add or update

- `tests/test_fleet_lease_broker.py`: claim of a worktree-declared reservation without a
  resolvable worktree_root raises LeaseBrokerError (no unfenced grant).

### Verification

```
uv run pytest -q tests/test_fleet_lease_broker.py
```

### Objective

Not yet assigned to an Objective — pre-existing edge confirmed by the #643 code review (finding 2); grouping is the operator's call.

### Intent

Declared-worktree isolation always yields a fence or a loud refusal — never a silent unfenced grant.

### Out-of-scope / non-goals

Adapter-side changes (the shipped saga adapter cannot reach this edge); declared-write-roots grants (KTD4 follow-up).

### Context library links

- docs/code-reviews/2026-07-23-issue-616-worktree-write-fence-scoping-code-review.md (finding 2)

### Acceptance criteria

- [ ] Claim of an `isolation='worktree'` reservation without a resolvable worktree_root raises LeaseBrokerError.
- [ ] Regression test pins the refusal; existing worktree fence tests stay green.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: /private/tmp/claude-501/-Users-jefcox-workspace-infiquetra-infiquetra-claude-plugins/a2c17e16-6a69-4ff8-a9f6-dc347823861a/scratchpad/issue-bodies/unfenced-edge.md
- Source type: local-file
- Source title: unfenced-edge

### Recommended Tier Band
opus/high

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/647
- Number: 647
- Created at: 2026-07-23T12:07:11.768441+00:00

