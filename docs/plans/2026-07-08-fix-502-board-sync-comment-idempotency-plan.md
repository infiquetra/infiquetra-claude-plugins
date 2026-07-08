---
title: Prevent duplicate saga board-sync progress comments — issue #502
type: fix
status: active
date: 2026-07-08
origin: https://github.com/infiquetra/infiquetra-claude-plugins/issues/502
---

# Prevent Duplicate Saga Board-Sync Progress Comments — Issue #502

## Summary

`board_progression.authorize_and_write` posts GitHub side effects before it writes the local
board-sync idempotency ledger. That order is retryable for idempotent board writes, but additive
`issue-progress-comment` writes can duplicate if the process crashes after the comment POST and
before the ledger file is written. `outcome_reconcile` does not reread comments, so the duplicate is
silent and cannot be healed by reconcile.

## Requirements

R1. Every saga board-sync progress comment must carry a deterministic, hidden idempotency marker
derived from the same ledger key that coalesces the operation.

R2. The production board writer must check existing issue comments for that marker before posting
and skip the POST when the marker already exists.

R3. A replay after a post-before-ledger crash must be able to observe the marker, avoid a duplicate
comment, and then let `authorize_and_write` write the missing ledger key.

R4. Non-comment board operations must keep their existing behavior.

R5. Existing visible progress-comment prose must remain readable; the marker must not replace the
operator-facing text.

R6. Tests must cover marker injection and production-writer skip behavior without live GitHub I/O.

R7. Saga release surfaces must be updated because autonomous board-sync behavior changes.

## Key Technical Decisions

**KTD1: Marker at the shared mechanism boundary.** `authorize_and_write` already computes the
canonical idempotency key. It will append a deterministic HTML marker to `issue-progress-comment`
payloads before invoking `board_writer`, keeping the marker recipe single-sourced against the ledger
key and available to any writer implementation.

**KTD2: Production writer performs the live dedupe read.** The injected writer boundary is the only
place that knows how to talk to GitHub. `default_board_writer` will check the issue's recent comments
for the marker before running mission-control's `issue comment` command. If found, it returns
success so `authorize_and_write` can persist the missing ledger key.

**KTD3: Leave reconcile scope unchanged.** Reconcile remains status/open-state oriented. The marker
preflight closes the crash replay hole without adding comment history scans to reconcile's existing
drift model.

## Implementation Units

### U1. Shared marker helper

Add small helpers in `plugins/saga/scripts/board_progression.py` to derive a stable marker from a
ledger key and append it to comment bodies exactly once.

### U2. Authorize/write payload mutation

When `op_kind == "issue-progress-comment"`, append the marker to `payload["body"]` before invoking
`board_writer`. Include the marker in the `pay` copy only; do not mutate the caller's original
payload object.

### U3. Production writer dedupe

Before posting a marked `issue-progress-comment`, have `default_board_writer` read the issue comments
with `gh api`, scan for the marker, and return without posting when present. If the read fails, raise
so the existing bounded retry/fail-loud path handles the transient failure.

### U4. Tests

Update board progression and outcome board-sync tests to assert:

- comment payloads receive a hidden marker derived from the ledger key,
- non-comment payloads are unchanged,
- the production writer posts when the marker is absent,
- the production writer skips the post when the marker is already present,
- the replay path can skip an existing remote comment and then write the missing local ledger key.

### U5. Release surfaces

Bump saga metadata, update changelog, regenerate marketplace metadata, and run release-surface
guards.

## Scope Boundaries

Out of scope: changing the ordering of all board writes, adding a two-phase ledger protocol, changing
`outcome_reconcile` drift kinds, or attempting to delete existing duplicate comments.

## Verification

- `uv run pytest tests/test_board_progression.py tests/test_outcome_board_sync.py -v`
- `uv run python -m ruff check plugins/saga/scripts/board_progression.py plugins/saga/scripts/outcome_board_sync.py tests/test_board_progression.py tests/test_outcome_board_sync.py`
- `uv run python -m ruff format --check plugins/saga/scripts/board_progression.py plugins/saga/scripts/outcome_board_sync.py tests/test_board_progression.py tests/test_outcome_board_sync.py`
- `uv run python -m mypy plugins/saga/scripts/board_progression.py plugins/saga/scripts/outcome_board_sync.py tests/test_board_progression.py tests/test_outcome_board_sync.py --ignore-missing-imports`
- `python3 scripts/check_release_surface_parity.py`
- `uv run python scripts/sync_marketplace.py --check`
- `python3 tools/release_surface_diff_guard.py --base-ref origin/main`
- `git diff --check`
