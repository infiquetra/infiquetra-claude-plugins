---
title: defect(fleet): PostToolUse fires at async-spawn launch and releases the unclaimed reservation + session admission (race with SubagentStart claim)
repo: infiquetra-claude-plugins
type: defect
team: asgard
project: operations
status: Shaping
labels: defect, hermes-task, needs-plan
risk: high
handoff_maturity: requirements-ready
approval_state: needs_operator_approval
---

# defect(fleet): PostToolUse fires at async-spawn launch and releases the unclaimed reservation + session admission (race with SubagentStart claim)

## Problem

With the harness launching Agent/Task subagents asynchronously (tool result returns at launch,
not completion), the PostToolUse[Agent|Task] lifecycle hook destroys the child's lease before
the child can claim it, roughly half the time. Three consecutive live spawns failed during the
#616 R8 rollout canary (2026-07-23); a 100 ms registry watcher showed the healthy PreToolUse
reservation and the session admission wiped in a single write 101-156 ms after reservation —
exactly when the async Agent call returned its launch metadata.

## Mechanism (pinned, line-anchored at fleet-core 0.20.0)

PostToolUse -> `record_hook_parent` (saga adapter `lease_broker.py:379-394`) -> broker
`record_parent_completed` (`fleet_commons/lease_broker.py:3895`):
- a matching lease with `agent_id is None` (reservation not yet claimed) is treated as
  "spawn never happened" and removed via `_complete_foreground_lease` (:3913-3921);
- if the session then has no live agents, its admission is popped in the same write
  (:3924-3927).

The contract assumes PostToolUse is a completion signal. For async spawns it is a launch
signal, so the cleanup races SubagentStart's claim; when cleanup wins the child runs unbound
and every delegated mutation is refused ("expected exactly one fleet lease bound; found 0").
Same signature as the 3-of-8 verifier lease losses during the #616 code review, and a strong
suspect for the pass-4 whole-batch disappearance at first child terminal (work-session doc).

## Acceptance sketch

- A reservation younger than the spawn round-trip is never destroyed by PostToolUse; either
  distinguish launch-return from completion-return, or defer unclaimed-reservation cleanup to
  a claim-window TTL that SubagentStart can win deterministically.
- Session admission is not popped while an unclaimed, unexpired reservation exists.
- Live canary: N consecutive async spawns all bind and mutate under armed hooks.

## Evidence

- `docs/work-sessions/2026-07-22-issue-616-worktree-write-fence-scoping.md` (post-merge R8 section)
- LEARNINGS `{#async-spawn-posttooluse-race-616-r8}` (commit 277f070d)
- Registry timelines: session scratchpad `registry_timeline.log` / `registry_timeline2.log`

### Files expected to change

- `plugins/fleet-core/scripts/fleet_commons/lease_broker.py` — `record_parent_completed`
  unclaimed-reservation handling (:3895-3928) and/or a claim-window grace seam
- `plugins/saga/scripts/lease_broker.py` — `record_hook_parent` if launch/completion
  disambiguation lands adapter-side
- Release surfaces: both plugin.json, marketplace.json, CHANGELOGs, drift pins

### Tests to add or update

- `tests/test_fleet_lease_broker.py`: parent-completed against an unclaimed, unexpired
  reservation must not remove it; admission survives while such a reservation exists;
  claim-after-parent-completed within the grace window binds.

### Verification

```
uv run pytest -q tests/test_fleet_lease_broker.py tests/test_saga_hooks.py
# live: N consecutive async Agent spawns under armed hooks all bind and mutate
```

### Objective

Not yet assigned to an Objective — surfaced during the governed-execution-integrity (#639) #616 R8 rollout canary; grouping is the operator's call.

### Intent

Make the Agent/Task lease lifecycle correct for asynchronous spawns: PostToolUse at launch-return must never destroy a claimable reservation or the session admission.

### Out-of-scope / non-goals

Redesigning admission policy or lease TTLs (see the TTL lifecycle defect); workflow batch-slot recycle semantics beyond what the race touches; harness-side changes to spawn synchrony.

### Context library links

- docs/work-sessions/2026-07-22-issue-616-worktree-write-fence-scoping.md (post-merge R8 section)
- docs/engineering-journal/LEARNINGS.md `{#async-spawn-posttooluse-race-616-r8}`

### Acceptance criteria

- [ ] `uv run pytest -q tests/test_fleet_lease_broker.py -k parent_completed` green, including a new test where `record_parent_completed` against an unclaimed, unexpired reservation leaves the lease claimable and the session admission intact.
- [ ] `uv run pytest -q tests/test_fleet_lease_broker.py -k claim` green, including claim-after-parent-completed inside the grace window binding successfully.
- [ ] Live canary: 10 consecutive async Agent spawns under armed installed hooks all bind and complete a delegated `Write` — 0 occurrences of `expected exactly one fleet lease bound; found 0`.

### Inputs inventory

- fleet-core 0.20.0 `fleet_commons/lease_broker.py` (`record_parent_completed` :3895-3928)
- saga 0.111.0 `scripts/lease_broker.py` (`record_hook_parent` :379-394)
- Registry watcher timelines (session scratchpad `registry_timeline.log` / `registry_timeline2.log`)
- Hook registration map: saga `hooks/hooks.json` (PostToolUse[Agent|Task] + SubagentStart both -> lease_lifecycle_hook)

### Failure modes / pre-mortem

- Grace-window too long: truly abandoned reservations (spawn errored pre-start) linger and eat admission slots until claim TTL expiry — bound the window to the claim TTL, never beyond.
- Distinguishing launch vs completion from hook payload may be impossible harness-side today; fallback design must be broker-side (age gate), not payload-sniffing.
- Fixing only the lease removal but not the admission pop leaves half the race (children bind but the session loses its admission for the NEXT spawn).

### Stop conditions

- If the harness exposes an explicit completion event for async spawns, prefer wiring that signal over an age heuristic — stop and re-plan.
- If a fix requires registry schema additions, it must land after or with #617 read-tolerance, never before.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: /private/tmp/claude-501/-Users-jefcox-workspace-infiquetra-infiquetra-claude-plugins/a2c17e16-6a69-4ff8-a9f6-dc347823861a/scratchpad/issue-bodies/async-race.md
- Source type: local-file
- Source title: live: N consecutive async Agent spawns under armed hooks all bind and mutate

### Recommended Tier Band
opus/high

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/644
- Number: 644
- Created at: 2026-07-23T12:06:36.515683+00:00

