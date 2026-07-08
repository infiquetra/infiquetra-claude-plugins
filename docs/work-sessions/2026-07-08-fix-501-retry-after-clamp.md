# Work session — Retry-After clamp (#501)

- **Date:** 2026-07-08
- **Issue:** #501 — `fleet-commons: Retry-After hint bypasses max_delay clamp`
- **Plan:** `docs/plans/2026-07-08-fix-501-retry-after-clamp-plan.md`
- **Doc-review:** `docs/reviews/2026-07-08-fix-501-retry-after-clamp-plan-doc-review.md`
- **Code-review:** `docs/code-reviews/2026-07-08-fix-501-retry-after-clamp-code-review.md`
- **Backend:** inline autonomous defect loop.

## What Shipped

Fleet-core's shared `retry_with_backoff` primitive now bounds server-supplied retry hints.

- Extracted computed jittered backoff into `_computed_delay`.
- Added `_retry_delay` so positive `Retry-After` hints are capped at `max_delay`.
- Treats zero and negative hints as absent, falling back to computed jittered backoff and avoiding
  tight retry loops.
- Preserved no-hint jitter behavior and the existing positive hint override shape.
- Added tests for oversized, zero, and negative hints.
- Updated fleet-core release surfaces to `0.8.1`.

## Gates

- `uv run pytest tests/test_retry_backoff.py -v`
- `uv run python -m ruff check plugins/fleet-core/scripts/fleet_commons/retry_backoff.py tests/test_retry_backoff.py`
- `uv run python -m ruff format --check plugins/fleet-core/scripts/fleet_commons/retry_backoff.py tests/test_retry_backoff.py`
- `uv run python -m mypy plugins/fleet-core/scripts/fleet_commons/retry_backoff.py tests/test_retry_backoff.py --ignore-missing-imports`
- `python3 scripts/check_release_surface_parity.py`
- `uv run python scripts/sync_marketplace.py --check`
- `python3 tools/release_surface_diff_guard.py --base-ref origin/main`
- `git diff --check`

## Residual Risk

Downstream byte-identical ports, including the Codex plugin copy called out in the issue, still need
to resync from this canonical fleet-core implementation after merge.
