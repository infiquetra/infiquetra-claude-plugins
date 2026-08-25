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
# Negative delta-seconds Retry-After yields a negative wait time

## Intent

`parse_retry_after` in `plugins/fleet-core/scripts/fleet_commons/retry_backoff.py` returns a
negative number for a negative delta-seconds header, contradicting its own docstring, which
states: "A date already in the past yields `0.0` — retry now, never a negative delay." The
HTTP-date path honours that contract; the delta-seconds path does not. A caller that reduces
the hint to whole seconds to advise an operator therefore prints a negative wait time.

Observed on fleet-core 0.25.2, CPython 3.12.13, with no network call:

| `Retry-After` | `parse_retry_after` | operator sees |
|---|---|---|
| `-5` | `-5.0` | `Rate limited. Retry after -5 seconds` |
| `-120` | `-120.0` | `Rate limited. Retry after -120 seconds` |
| past HTTP-date | `0.0` | `Rate limited. Retry after 0 seconds` |

The sleep path is unaffected: `_retry_delay` rejects a non-positive hint and falls back to
computed jittered backoff, so no tight retry loop is possible. The damage is confined to the
advice value surfaced in a caller's typed 429 error.

Pre-existing since 0.25.1, when `parse_retry_after` was introduced. Not introduced by 0.25.2,
which added a non-finite guard but not a negative one.

## Acceptance criteria

- `python3 -c "import sys; sys.path.insert(0,'plugins/fleet-core/scripts'); from fleet_commons import retry_backoff as rb; print(rb.parse_retry_after('-5'))"` prints `0.0`, not `-5.0`.
- `python3 -c "import sys; sys.path.insert(0,'plugins/fleet-core/scripts'); from fleet_commons import retry_backoff as rb; print(rb.parse_retry_after('-120'))"` prints `0.0`.
- Existing behaviour is unchanged: `python3 -c "import sys; sys.path.insert(0,'plugins/fleet-core/scripts'); from fleet_commons import retry_backoff as rb; print(rb.parse_retry_after('30'), rb.parse_retry_after('1e400'), rb.parse_retry_after('garbage'))"` prints `30.0 None None`.
- `python3 -m pytest tests/test_retry_backoff.py -q` reports all tests passing.

## Out-of-scope / non-goals

- No change to the sleep path. `_retry_delay` already refuses a non-positive hint and its
  fallback to computed jittered backoff is correct; this defect is about the advice value only.
- No change to the non-finite guard added in 0.25.2.
- No change to any consumer. The fix belongs at the single chokepoint in the primitive so every
  caller inherits it; editing a caller instead would leave the contract violated for the others.
- Not a security or availability defect, and not a release blocker for any consumer.

## Files expected to change

- `plugins/fleet-core/scripts/fleet_commons/retry_backoff.py`
- `tests/test_retry_backoff.py`
- `plugins/fleet-core/CHANGELOG.md`
- `plugins/fleet-core/.claude-plugin/plugin.json`

## Tests to add or update

- Add a parametrised case in `tests/test_retry_backoff.py` asserting `parse_retry_after` returns
  `0.0` for `-5`, `-0.5`, and `-120`, mirroring the existing past-HTTP-date test so both paths
  are pinned to the same documented answer.
- Extend the existing postcondition test so every hint the function returns is non-negative as
  well as finite, which states the contract once rather than enumerating spellings.
- Confirm the new assertions fail against the unrepaired primitive before the fix lands.

## Verification

```bash
python3 -m pytest tests/test_retry_backoff.py -q
python3 -c "
import sys; sys.path.insert(0, 'plugins/fleet-core/scripts')
from fleet_commons import retry_backoff as rb
for h in ('-5', '-0.5', '-120', '30', '1e400', 'garbage'):
    print(h, '->', rb.parse_retry_after(h))
"
ruff check plugins/fleet-core/scripts/fleet_commons/retry_backoff.py
python3 scripts/check_release_surface_parity.py
```

Expected: negatives reduce to `0.0`, `30` stays `30.0`, `1e400` and `garbage` stay `None`, the
suite is green, lint is clean, and release surfaces stay in parity.

## Provenance

Found by an independent reviewer (OpenCode Ox Alpha, max effort) during the fifth review cycle
of the UniFi portability pilot in `infiquetra-agent-plugins`, and independently reproduced
before filing. Deferred out of that pilot by operator decision because it is pre-existing and
is neither a security nor a compatibility blocker; it is tracked here, in the repository that
owns the code.

### Intent

`parse_retry_after` returns a negative number for a negative delta-seconds header,
contradicting its own docstring: "A date already in the past yields `0.0` — retry now, never
a negative delay." The HTTP-date path honours that; the delta-seconds path does not. A caller
reducing the hint to whole seconds to advise an operator prints a negative wait time —
`Rate limited. Retry after -5 seconds`. Clamp the delta-seconds path to `0.0` so both paths
give the documented answer, at the single chokepoint every caller inherits.

### Out-of-scope / non-goals

- No change to the sleep path. `_retry_delay` already refuses a non-positive hint and falls
  back to computed jittered backoff; this defect concerns the advice value only.
- No change to the non-finite guard added in 0.25.2.
- No change to any consumer. The fix belongs in the primitive so every caller inherits it;
  repairing a caller would leave the contract violated for the others.
- Not a security or availability defect, and not a release blocker for any consumer.

### Files expected to change

- `plugins/fleet-core/scripts/fleet_commons/retry_backoff.py`
- `tests/test_retry_backoff.py`
- `plugins/fleet-core/CHANGELOG.md`
- `plugins/fleet-core/.claude-plugin/plugin.json`

### Tests to add or update

- Add a parametrised case in `tests/test_retry_backoff.py` asserting `parse_retry_after`
  returns `0.0` for `-5`, `-0.5`, and `-120`, mirroring the existing past-HTTP-date test so
  both paths are pinned to the same documented answer.
- Extend the existing postcondition test so every returned hint is non-negative as well as
  finite, stating the contract once rather than enumerating spellings.
- Confirm the new assertions fail against the unrepaired primitive before the fix lands.

### Context library links
- source_context: /private/tmp/claude-501/-Users-jefcox-workspace-infiquetra-infiquetra-agent-plugins/754b6091-9bb0-46dc-88b2-e00814b02fd8/scratchpad/fleet-core-negative-retry-after.md

### Acceptance criteria

- [ ] `python3 -c "import sys; sys.path.insert(0,'plugins/fleet-core/scripts'); from fleet_commons import retry_backoff as rb; print(rb.parse_retry_after('-5'))"` prints `0.0`, not `-5.0`.
- [ ] The same call with `-120` prints `0.0`.
- [ ] Existing behaviour is unchanged: `30` still yields `30.0`, `1e400` and `garbage` still yield `None`.
- [ ] `python3 -m pytest tests/test_retry_backoff.py -q` reports all tests passing.
- [ ] The new assertions fail against the unrepaired primitive, proving they bite.

### Verification

```bash
python3 -m pytest tests/test_retry_backoff.py -q
python3 -c "
import sys; sys.path.insert(0, 'plugins/fleet-core/scripts')
from fleet_commons import retry_backoff as rb
for h in ('-5', '-0.5', '-120', '30', '1e400', 'garbage'):
    print(h, '->', rb.parse_retry_after(h))
"
ruff check plugins/fleet-core/scripts/fleet_commons/retry_backoff.py
python3 scripts/check_release_surface_parity.py
```

Expected: negatives reduce to `0.0`, `30` stays `30.0`, `1e400` and `garbage` stay `None`, the
suite is green, lint is clean, and release surfaces stay in parity.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: /private/tmp/claude-501/-Users-jefcox-workspace-infiquetra-infiquetra-agent-plugins/754b6091-9bb0-46dc-88b2-e00814b02fd8/scratchpad/fleet-core-negative-retry-after.md
- Source type: local-file
- Source title: Negative delta-seconds Retry-After yields a negative wait time

### Recommended Tier Band
opus/high
