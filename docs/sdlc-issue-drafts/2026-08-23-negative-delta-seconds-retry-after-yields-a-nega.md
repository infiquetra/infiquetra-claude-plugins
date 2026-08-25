---
title: negative delta-seconds Retry-After yields a negative wait time, contradicting the primitive's contract
repo: infiquetra-claude-plugins
type: defect
team: asgard
project: operations
status: Shaping
labels: defect, needs-plan
risk: low
handoff_maturity: requirements-ready
---

# negative delta-seconds Retry-After yields a negative wait time, contradicting the primitive's contract

### Objective
# Negative delta-seconds Retry-After reaches the operator as a negative wait time

`parse_retry_after` in `plugins/fleet-core/scripts/fleet_commons/retry_backoff.py`
returns a negative number for a negative delta-seconds header, contradicting the
function's own documented contract.

## The contract it violates

The docstring states: "A date already in the past yields `0.0` — retry now, never a
negative delay." The HTTP-date path honours that. The delta-seconds path does not.

## Reproduction

Observed on fleet-core 0.25.2, CPython 3.12.13, no network call:

| `Retry-After` | `parse_retry_after` | `math.ceil` of it | Operator sees |
|---|---|---|---|
| `-5` | `-5.0` | `-5` | `Rate limited. Retry after -5 seconds` |
| `-120` | `-120.0` | `-120` | `Rate limited. Retry after -120 seconds` |
| past HTTP-date | `0.0` | `0` | `Rate limited. Retry after 0 seconds` |

The sleep path is unaffected: `_retry_delay` rejects a non-positive hint and falls back
to computed jittered backoff, so no tight retry loop is possible. The damage is confined
to the advice value a caller reduces to whole seconds after retries are exhausted, which
both UniFi clients surface in their typed 429 error.

## Suggested fix

`_usable_delay` already screens non-finite values. Clamping a negative result to `0.0`
there would make the delta-seconds path agree with the HTTP-date path and with the
docstring, in one place, for every caller.

## Provenance

Pre-existing since fleet-core 0.25.1, when `parse_retry_after` was introduced. Not
introduced by 0.25.2, which added the non-finite guard but not a negative one.

Found by an independent reviewer (OpenCode Ox Alpha, max effort) during the fifth review
cycle of the UniFi portability pilot in `infiquetra-agent-plugins`, and independently
reproduced before filing. Deferred out of that pilot by operator decision because it is
pre-existing and is neither a security nor a compatibility blocker; it is tracked here,
in the repository that owns the code.

### Intent
_No response_

### Out-of-scope / non-goals
_No response_

### Files expected to change
_No response_

### Tests to add or update
_No response_

### Context library links
- source_context: /private/tmp/claude-501/-Users-jefcox-workspace-infiquetra-infiquetra-agent-plugins/754b6091-9bb0-46dc-88b2-e00814b02fd8/scratchpad/fleet-core-negative-retry-after.md

### Acceptance criteria
- [ ] _No response_

### Verification
_No response_

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: /private/tmp/claude-501/-Users-jefcox-workspace-infiquetra-infiquetra-agent-plugins/754b6091-9bb0-46dc-88b2-e00814b02fd8/scratchpad/fleet-core-negative-retry-after.md
- Source type: local-file
- Source title: Negative delta-seconds Retry-After reaches the operator as a negative wait time

### Recommended Tier Band
opus/high
