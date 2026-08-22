# Work session — Retry-After HTTP-date handling in fleet-core (review finding O3)

- **Thread:** saga `task-fleetcore-retry-after-http-date`, `lifecycle_phase=work`
- **Branch:** `orch/orch-2026-08-22-fleetcore-retryafter-o3-fleetcore-retry-after`
- **Destination:** pr
- **Execution backend:** inline — decided before the run and recorded, not offered
- **Release:** fleet-core `0.25.0` -> `0.25.1`

## The defect

RFC 7231 section 7.1.3 allows `Retry-After` in two forms: delta-seconds and an absolute HTTP-date.
fleet-core's shared 429 primitive only ever understood a number, so a caller that reduced the header
to seconds itself raised `ValueError` on the date form — inside the callable `retry_with_backoff`
guards. `retry_with_backoff` classifies an error by `status_code` / `status`; a `ValueError` carries
neither, so it read as non-retryable and propagated on the first attempt. The caller's typed
rate-limit handler does not catch `ValueError` either, so the operator saw a generic error and got one
request with no backoff — the opposite of the primitive's purpose.

Both cycle-1 reviewers found this independently and cycle 2 reconfirmed it.

## Why the fix lands here

`retry_backoff.py` is carried downstream in `infiquetra-agent-plugins` as an upstream **byte copy**.
Patching the downstream copy would create a second writable source, so custody stays here: fix
upstream, release, then resynchronize downstream as a separate step.

## What changed (U1)

`plugins/fleet-core/scripts/fleet_commons/retry_backoff.py`

- New public `parse_retry_after(value, *, now=time.time) -> float | None`. Accepts an already-numeric
  hint unchanged, a delta-seconds string, and all three date forms `email.utils.parsedate_to_datetime`
  covers (IMF-fixdate, obsolete RFC 850, asctime — whose missing zone is read as GMT per the
  specification). Absent, empty, non-string, boolean, and unparseable values return `None`, meaning
  "no usable hint".
- `retry_with_backoff` routes the hint through the parser, so its `retry_after` callable may now
  return the raw header string; its type widens to `float | str | None` (additive).
- New keyword-only `now` seam (epoch seconds, default `time.time`) so an HTTP-date resolves
  deterministically under test. Distinct from `CircuitBreaker`'s monotonic `clock`; `bridge_call`
  forwards it through `**retry_kwargs`.
- `_retry_delay` is untouched: clamp and jitter behave exactly as before, so an absurd date and an
  absurd number are bounded by `max_delay` on the same line of code.

### Key decision — what "a date in the past" does

A past date parses to `0.0`, never a negative delay. The existing non-positive-hint rule (fleet-core
0.8.1, issue #501) then answers with computed jittered backoff. Sleeping literally zero would
reintroduce exactly the tight retry loop 0.8.1 was written to prevent, so "retry now" is honored as
the minimum non-negative parse and the delay policy stays where 0.8.1 put it.

### Key decision — patch, not minor

Bumped `0.25.0` -> `0.25.1`. The change adds a public function, which strict semantic versioning would
call a minor bump; the run's instruction named it a bug fix, and fleet-core 0.8.1 set the precedent for
this same file. In `0.x`, additive-only is the standing contract either way.

## Tests (U2)

`tests/test_retry_backoff.py`, against a frozen wall clock (`NOW = 1700000000.0`) so every date
fixture resolves identically on every run:

| Case | Test | Assertion |
| --- | --- | --- |
| delta-seconds, unchanged | `test_delta_seconds_hint_is_unchanged_numeric_and_string` | `30` and `"30"` both sleep `30.0` |
| valid future HTTP-date | `test_future_http_date_is_honored_as_the_seconds_remaining` | parses to `45.0`, sleeps `45.0` |
| past HTTP-date | `test_past_http_date_means_retry_now_never_a_negative_delay` | parses to `0.0`, falls back to jittered backoff |
| unparseable value | `test_unparseable_retry_after_falls_back_to_computed_backoff` | parses to `None`, falls back to jittered backoff |
| excessive date | `test_excessive_http_date_is_clamped_to_max_delay` | parses honestly, sleeps `max_delay` |

Plus `test_all_three_http_date_forms_parse`, `test_values_that_are_not_a_delay_parse_to_none`, and
`test_a_caller_that_pre_parses_with_int_still_loses_the_retry` — the last a characterization test that
pins this repair's boundary (see below).

## Deliberately out of scope — the residual

Both UniFi clients still call `int(resp.headers.get("Retry-After", 60))` before raising
(`unifi_network_client.py:174`, `unifi_protect_client.py:174`). They are the primitive's only two
consumers, and until they hand the raw header to `retry_after` they keep converting it themselves and
remain exposed to this defect. That change belongs to the UniFi plugin and would require its own
release surfaces; this run was scoped to fleet-core and to a single fleet-core version bump. The
boundary is pinned by a test rather than left to prose.

## Checks run

`pytest` (full suite with coverage) · `ruff check` · `ruff format --check` · `mypy` ·
`check_release_surface_parity.py` · `sync_marketplace.py --check` · `lint_journal_order.py` ·
the full `scripts/gate.sh`.

## Next step

Open the PR; the controller merges. Then resynchronize the downstream byte copy in
`infiquetra-agent-plugins`, and separately repair the two UniFi call sites.
