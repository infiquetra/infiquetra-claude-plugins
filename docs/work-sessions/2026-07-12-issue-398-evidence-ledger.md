# Work Session — Issue #398: content-addressed evidence ledger (2026-07-12)

One-line summary: built `evidence_ledger.py` (content-addressed write-once artifacts, hash-chained
custody log with a head pointer, frozen criteria, closure verify with role separation), wired
`/qa` and `/code-review` through it, bumped saga to 0.81.0, and reached PR-ready with a clean
full-suite gate.

## What was built (by U-ID)

- **U1** — Core ledger: `write()` content-addresses the artifact (sha256), stores it write-once
  via `outcome_store._write_once`, and appends a hash-chained JSONL custody entry.
  `verify_chain()` re-derives linkage and re-hashes every referenced file. Discovered during
  testing: a pure `prev`-hash chain cannot detect tampering with the *last* entry (no successor
  to check it against) — added `ledger.head`, an atomically-updated pointer to the tail entry's
  hash, closing that gap. This is exactly the grounding incident's shape (a probe script silently
  overwrote a FAIL artifact), so the fix stayed in scope rather than becoming a follow-up.
- **U2** — `freeze_criteria()` (write-once per `(check_id, reviewed_sha)`, rejects a second
  freeze even with identical content — freezing is an intent-capture event, not a value cache)
  and `latest()` (groups by identity, flags a FAIL→PASS transition as `superseded_fail`).
- **U3** — `close_verify()`: full chain re-verify (HALTs on any tamper), then rejects a verifier
  whose role matches the `(check_id, reviewed_sha)` producer. Scoped per-check rather than
  ledger-wide — refined from the plan's original wording during implementation, matching the
  acceptance criterion's own "for that check" framing and sub-397's future per-check closure gate
  (recorded in the plan's KTD4).
- **U4** — `/qa` Phase 2 (criteria freeze) + Phase 5.1 (ledger write, replacing the bare
  `docs/qa/*.md` write) and `/code-review` Phase 1.5 (criteria freeze, interactive-only) +
  Phase 5.3 (ledger write, replacing `docs/code-reviews/*.md`). Both skills fall back to
  `docs/evidence/adhoc-<branch-slug>/` when no work-thread saga exists — only the saga tick is
  skipped in that case, never the ledger write. Programmatic/report-only `/code-review` is
  unchanged (zero writes of any kind).
- **U5** — saga 0.80.0 → 0.81.0 (`plugin.json`), `marketplace.json` regenerated via
  `scripts/sync_marketplace.py` (never hand-edited), `CHANGELOG.md` entry, drift-guard tests
  re-run green.

## Checks run

- `tests/test_evidence_ledger.py`: 19/19 passed, 95% coverage on the new module (all 7 named
  `-k` scenarios from the issue, plus traversal-id rejection, torn-tail rejection, and the
  no-saga adhoc-fallback CLI path).
- Drift guard: `test_sync_marketplace.py` / `test_marketplace_hook.py` /
  `test_changelog_heading_lint.py` / `test_agent_registration_drift.py`: 40/40 passed.
- Full repo gate at `227245d` (pre-U5) and again post-U5: `ruff format --check .` clean,
  `ruff check .` clean, `mypy plugins/ scripts/ tests/ --ignore-missing-imports` clean (190
  files), `bandit -r plugins/saga/scripts/evidence_ledger.py` zero issues.
- Full suite: 3350 passed / 0 failed / 1 skipped (pre-U5 baseline); re-confirmed post-U5.

## Commits (branch `work/398-evidence-ledger`, PR #567)

- `ae87f38` docs(plan): issue #398 evidence ledger plan, doc-review, KTD record
- `227245d` feat(saga): content-addressed evidence ledger for /qa and /code-review (#398)
- (U5 release-surface commit — see saga.py tick for the exact SHA)

## Process notes

- The plan under-specified two things that surfaced only while writing tests: the hash-chain's
  lone-tail-tamper gap (fixed with `ledger.head`) and `close_verify`'s scope (per-check, not
  ledger-wide). Both are recorded back into the plan doc and the DECISIONS.md KTD entry so they
  read as decisions, not gaps.
- Kept `write()` simple by NOT re-validating frozen-criteria hash consistency on every write —
  that check lives in `verify_chain()`/`close_verify()` instead, since `_write_once` already
  makes the criteria file itself un-editable after the freeze; duplicating the check in `write()`
  would have been redundant defense with no additional guarantee.

## Next step

Draft PR #567 has the plan+review+KTD commit and the implementation commit. Run `/code-review`
programmatically for the pre-PR gate, then offer to flip the PR ready + request review.
