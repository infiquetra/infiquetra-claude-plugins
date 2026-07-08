---
title: Clamp Retry-After hints in fleet-core backoff — issue #501
type: fix
status: active
date: 2026-07-08
origin: https://github.com/infiquetra/infiquetra-claude-plugins/issues/501
---

# Clamp Retry-After Hints In Fleet-Core Backoff — Issue #501

## Summary

`fleet_commons.retry_backoff.retry_with_backoff` clamps computed exponential delays to
`max_delay`, but the server-supplied `Retry-After` hint path uses `float(hint)` directly. A
misbehaving endpoint can therefore force an unbounded sleep, and `Retry-After: 0` can create a tight
retry loop.

## Requirements

R1. Positive `Retry-After` hints must be capped at `max_delay`.

R2. Non-positive hints must not create zero-delay retry loops.

R3. Non-positive hints should fall back to the computed jittered backoff for that attempt.

R4. Existing computed-backoff behavior must remain unchanged when no hint is present.

R5. Tests must cover overlarge, zero, and negative hints.

R6. Fleet-core release surfaces must be updated because the shared primitive behavior changes.

## Key Technical Decisions

**KTD1: Clamp positive hints without jitter.** A positive server hint remains authoritative up to the
client's configured `max_delay`. This preserves the existing "hint overrides computed delay" shape
while preventing unbounded sleeps.

**KTD2: Treat non-positive hints as absent.** Falling back to computed jittered backoff prevents
tight loops and keeps retry pacing deterministic under the existing injected RNG seam.

## Implementation Units

### U1. Refactor delay selection

Add a small internal helper that computes the jittered backoff and applies the `Retry-After` rules:
positive hint -> `min(max_delay, hint)`; non-positive or absent hint -> computed jittered backoff.

### U2. Tests

Update `tests/test_retry_backoff.py` to assert:

- large hints clamp to `max_delay`,
- zero hints use computed jittered backoff,
- negative hints use computed jittered backoff,
- no-hint jitter bounds still hold.

### U3. Release surfaces

Bump `fleet-core` metadata and changelog, then regenerate/check marketplace metadata.

## Scope Boundaries

Out of scope: changing max-attempt semantics, changing the default `max_delay`, adding async retry
support, or syncing the downstream Codex plugin copy in this PR.

## Verification

- `uv run pytest tests/test_retry_backoff.py -v`
- `uv run python -m ruff check plugins/fleet-core/scripts/fleet_commons/retry_backoff.py tests/test_retry_backoff.py`
- `uv run python -m ruff format --check plugins/fleet-core/scripts/fleet_commons/retry_backoff.py tests/test_retry_backoff.py`
- `uv run python -m mypy plugins/fleet-core/scripts/fleet_commons/retry_backoff.py tests/test_retry_backoff.py --ignore-missing-imports`
- `python3 scripts/check_release_surface_parity.py`
- `uv run python scripts/sync_marketplace.py --check`
- `python3 tools/release_surface_diff_guard.py --base-ref origin/main`
