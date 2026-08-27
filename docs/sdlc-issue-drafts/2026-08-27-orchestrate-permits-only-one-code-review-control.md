---
title: Orchestrate permits only one Code Review controller per run so multi-lifecycle review fan-out is not representable
repo: infiquetra-claude-plugins
type: enhancement
team: asgard
project: operations
status: Shaping
labels: enhancement, needs-plan
risk: medium
mode: execute
handoff_maturity: requirements-ready
---

# Orchestrate permits only one Code Review controller per run, so multi-lifecycle review fan-out is not representable

### Objective

Let one run express several concurrent Code Review controllers, so a campaign with many independent
child lifecycles can review them in parallel within a single run record.

### Intent

`Run.review_controller` treats the review phase as strictly singular. When a run declares more than
one unit with `role: "review-controller"` it raises:

```
this run has more than one Code Review controller; one review phase is one
top-level Code Review invocation
```

That invariant is sound for the shape it was written for: a single body of work, reviewed once. It
becomes a hard wall for a campaign that runs **many independent child lifecycles inside one run**,
where each child needs its own review controller and several may be in review at the same time.

**Found during the Auralis preflight on installed Orchestrate 3.0.7.** The approved contract called
for a ceiling of **six concurrent Code Review controllers across fifteen child lifecycles**. That
shape cannot be written into `run.json` at all — not merely discouraged, not degraded, but rejected
at load. The operator's only representable options are to review the fifteen children serially
through one controller, or to split the campaign into fifteen runs, which the single fixed run
record makes its own problem.

This is a **product gap, not an operator configuration mistake**. The contract was approved and
coherent; the driver simply has no vocabulary for it.

Note the related-but-distinct constraint filed separately: the run record itself is a single fixed
path, so "just use more runs" is not currently available either.

### Out-of-scope / non-goals

- Do not weaken the single-controller invariant for runs that legitimately have one review phase;
  that default must stay.
- Do not change Code Review's own consensus protocol, lens selection, or cycle cap.
- Do not remove the guard entirely; an accidental second controller in a single-phase run should
  still be an error.
- Do not add cross-controller coordination or shared verdict state; each controller stays independent.

### Files expected to change

- `plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py`
- `plugins/orchestrate/skills/orchestrate/SKILL.md`
- `tests/test_orchestrate_settlement.py` or the review-transport test module
- Orchestrate release surfaces required by repository policy

### Tests to add or update

- A single-controller run keeps today's behaviour exactly, including the existing error when a
  second controller appears in a run that declares one review phase.
- A run declaring several controllers, each scoped to its own child lifecycle, loads and routes each
  review result to the right controller.
- A review result routed to the wrong controller is refused rather than silently accepted.
- The concurrency ceiling is honoured: declaring more concurrent controllers than the run permits is
  refused with a clear reason.
- Mutation-prove the routing: mis-binding a controller must fail a test.

### Context library links

- Current invariant: `plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py::Run.review_controller`
- Role constant: `REVIEW_CONTROLLER_ROLE`
- Discovery context: Auralis preflight on installed Orchestrate 3.0.7
- Prior review-transport work: issue 837, which fixed misclassification of role-less units
- The related single-run-record constraint, filed separately in this same retrospective

### Verification

```bash
uv run pytest tests/test_orchestrate_settlement.py -q
uv run ruff check plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py
GATE_LOG_DIR=/tmp/gate-run bash scripts/gate.sh > /tmp/gate.log 2>&1
cat /tmp/gate-run/result.txt
```

### Acceptance criteria

- [ ] A run can declare more than one Code Review controller when each is scoped to its own child lifecycle.
- [ ] Review results route to the correct controller, and a mis-routed result is refused.
- [ ] A single-phase run behaves exactly as it does today, error included.
- [ ] A declared concurrency ceiling on controllers is enforced.
- [ ] `bash scripts/gate.sh` exits 0 with Orchestrate release surfaces aligned.

### Notes / conventions

The invariant to preserve is "one review phase is one controller", not "one run is one controller".
Scoping a controller to a lifecycle rather than to the run keeps the original guarantee while
letting a campaign hold several lifecycles at once.

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/877
- Number: 877
- Created at: 2026-08-27T00:57:54.246902+00:00

