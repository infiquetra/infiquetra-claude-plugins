---
title: defect(saga,fleet): lease TTL lifecycle — read-only starvation, 30s claim TTL vs resume latency, renew_batch all-or-nothing
repo: infiquetra-claude-plugins
type: defect
team: asgard
project: operations
status: Shaping
labels: defect, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
approval_state: needs_operator_approval
---

# defect(saga,fleet): lease TTL lifecycle — read-only starvation, 30s claim TTL vs resume latency, renew_batch all-or-nothing

## Problem

Three related lease-TTL lifecycle defects, all reproduced across the five governed passes of
the #616 execution (work-session doc, findings 1 and 4):

1. **Execution-TTL starvation on read-only stretches.** `execution_ttl_seconds: 300` with
   mutation-only renewal means any unit whose tail is a long pytest run outlives its lease;
   expiry is fail-closed and unrecoverable for later spawns in the batch.
2. **30 s claim TTL loses to workflow-resume latency.** Unclaimed reserved slots lapse in
   30 s; a workflow resume replays cached agents before its first live spawn claims, so entire
   batches expire before first claim. Both values are hard-coded by the emitter in
   `_lease_reservation_metadata` (`plugins/saga/scripts/execution_spec.py` ~:3331).
3. **`renew_batch` is all-or-nothing and therefore structurally unusable with serialized
   units.** Any one expired member raises `LeaseExpiredError` and nothing renews; serialized
   units always leave unclaimed slots to lapse, so the driver renewal loop never succeeded in
   any pass.

## Working mitigations (proven in pass 5, all driver-side hacks)

Hand-editing `claim_ttl_seconds` 30->1800 in the driver-authored reservation metadata
(hash-safe; `policy_sha256` covers only the concurrency policy), plus a per-member keeper that
reconstructs each `FencingToken(broker_epoch, fencing_sequence)` from the raw registry and
calls `renew(lease_id, token=...)` individually, skipping expired members.

## Acceptance sketch

- Emitter TTLs (`claim_ttl_seconds`, `execution_ttl_seconds`) spec-configurable with sane
  defaults matched to observed resume/claim latency.
- Renewal on the read path or a broker-side heartbeat so read-only stretches do not starve.
- `renew_batch` gains a skip-expired mode returning per-member outcomes.

## Evidence

- `docs/work-sessions/2026-07-22-issue-616-worktree-write-fence-scoping.md` (durable machinery
  findings 1 and 4; pass 3/4/5 records)

### Files expected to change

- `plugins/saga/scripts/execution_spec.py` — `_lease_reservation_metadata` TTLs
  spec-configurable (~:3331)
- `plugins/fleet-core/scripts/fleet_commons/lease_broker.py` — read-path renewal or
  heartbeat; `renew_batch` skip-expired mode (:3785)
- Release surfaces for both plugins

### Tests to add or update

- `tests/test_saga_workflow_emitter.py`: spec-configured TTLs land in emitted metadata.
- `tests/test_fleet_lease_broker.py`: renew_batch skip-expired returns per-member outcomes;
  read-path renewal keeps a lease alive across a no-mutation window.

### Verification

```
uv run pytest -q tests/test_fleet_lease_broker.py tests/test_saga_workflow_emitter.py
# governed canary workflow with a long read-only unit survives without a driver keeper
```

### Objective

Not yet assigned to an Objective — consolidates durable findings 1 and 4 from the #616 governed execution; grouping is the operator's call.

### Intent

Governed workflow batches survive realistic execution shapes (long read-only stretches, slow resumes, serialized units) without driver-side keeper hacks.

### Out-of-scope / non-goals

The async PostToolUse race (separate defect); #617 schema read-tolerance; admission policy design.

### Context library links

- docs/work-sessions/2026-07-22-issue-616-worktree-write-fence-scoping.md (durable machinery findings 1 and 4; pass 3/4/5 records)

### Acceptance criteria

- [ ] Emitted reservation metadata honors spec-configured claim/execution TTLs.
- [ ] A lease under a read-only workload survives its full unit without mutation-driven renewal.
- [ ] `renew_batch` with one expired member renews the rest and reports per-member outcomes.
- [ ] A governed canary with a long read-only unit completes with no driver keeper.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: /private/tmp/claude-501/-Users-jefcox-workspace-infiquetra-infiquetra-claude-plugins/a2c17e16-6a69-4ff8-a9f6-dc347823861a/scratchpad/issue-bodies/ttl-lifecycle.md
- Source type: local-file
- Source title: governed canary workflow with a long read-only unit survives without a driver keeper

### Recommended Tier Band
opus/high

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/646
- Number: 646
- Created at: 2026-07-23T12:07:00.658743+00:00

