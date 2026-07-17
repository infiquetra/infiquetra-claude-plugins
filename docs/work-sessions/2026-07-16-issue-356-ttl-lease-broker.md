---
date: 2026-07-16
kind: work-session
issue: https://github.com/infiquetra/infiquetra-claude-plugins/issues/356
plan: docs/plans/2026-07-15-issue-356-ttl-lease-broker-plan.md
status: review-repair-complete-rereview-pending
---

# Work Session - Fleet TTL Lease Broker and Runtime Continuity

## Built

- U1: Added fleet-core's locked, closed-schema TTL lease authority with independent agent and
  worktree pools, normalized concurrency admission, atomic batch reservation, fencing-token
  supersession, cooperative renewal, exact release, and dead-owner sweep.
- U2: Installed Saga Agent/Task lifecycle and delegated-mutation hooks. Foreground release requires
  both trusted child-terminal and parent-return signals; stale, expired, missing, or superseded
  children cannot mutate through Bash or supported file tools.
- U3: Added Workflow batch metadata, all-or-nothing prelaunch reservation and attestation, hook
  claiming, cooperative renewal, and post-settlement release through `/work`.
- U4: Added team-execution preflight, renewal, and terminal-evidence teardown; wrapped registered
  external-engine and production outcome dispatch calls in read-only agent leases with redacted
  provenance.
- U5: Bound outcome-owned worktrees to separate pool receipts. Reconcile adopts legacy entries,
  renews live owners, and reaps only expired dead or reboot-invalidated owners through the canonical
  Saga reaper while retaining ambiguity and failures for retry.
- U6: Published lease protocol version 1 and fail-closed skew guards; expanded the machine-readable
  spawn inventory across Agent hooks, Workflow, team waves, engine/outcome dispatch, and worktrees;
  added operator recovery guidance; released fleet-core 0.12.0, Saga 0.99.0, and team-execution
  2.18.0 with aligned manifests, marketplace entries, changelogs, docs, tests, and journal learning.

## Verified Workflow

- Run: `record:workflow-run:9d1dfaf0b30a6c5f3e3be5f1bd31ca90556813f4062f874adebc500767fe8547`
- Subject: `record:subject:e997e3a1c57a84b9ee37f471d56a8ed6fd90789fd8457f0818e20bcddfd89933`
- Before snapshot:
  `record:workspace-snapshot:7423f6e49f3eb7e2ba64b82ea3bc57f7d7c09efb279f4445bb9f50539f1368c3`
- Intent: `record:intent:5a2dee5ed41ffbbbf2de7df54d2b2547077288d26c5a3834fd192ad9bf7cbb17`
- Approved plan digest: `62d5bff8e79f0330744f250358cbbc6910dcb82a7e31bf1a44f216747932430d`

## Commits

- `d8c62439` `feat(fleet-core): add lease admission authority`
- `9324a670` `feat(saga): fence delegated agent lifecycles`
- `8b96f70a` `feat(saga): reserve workflow lease batches`
- `1b2a9275` `feat(fleet): lease direct runtime dispatches`
- `e0766dd3` `feat(saga): lease outcome worktrees`
- U6 release/conformance commit follows this checkpoint in the same issue branch.

## Checks

- Focused U6 and release gate: 385 passed.
- Full suite after synchronized `uv sync --frozen --extra dev`: 4,618 passed, one skipped, eight
  multiprocessing deprecation warnings; 83% aggregate coverage.
- `uv run ruff check .`: passed.
- `uv run ruff format --check .`: passed.
- `uv run mypy plugins/`: passed.
- `uv run bandit -r plugins/`: reports two pre-existing high findings in unchanged files already on
  `origin/main`; the complete #356 changed Python surface has zero medium/high findings. CI records
  the same Bandit class as a nonblocking report.
- `git diff --check`: passed before the final checkpoint artifact.

## Next Step

Pin the repaired revision, rerun the affected whole-diff code-review lenses and independent
concurrency/event-flow validators, then run the full repository gate and open, monitor, and merge the
issue PR.

## Review Repair Round 1

- Repaired all 21 P0-P2 findings from
  `docs/code-reviews/2026-07-16-issue-356-ttl-lease-broker-code-review.md`.
- Durable outcome worktrees now transfer exact-token ownership to each one-shot coordinator before a
  lock-held sweep; active dispatched nodes veto destructive reap, and physical Git creation follows
  persisted registry/lease recovery authority.
- Agent sessions pin exact admission snapshots; nested parents are current-session verified; Workflow
  batches and resident sessions settle atomically from the required lifecycle signals.
- Registered second-opinion engines consume the configured Saga admission snapshot, use stable retry
  identity, and defer fact writes until post-run renew/verify. Cleanup failures preserve primary errors.
- Added synchronized hook/broker contention, negative lifecycle-call conformance, wrong-token refusal,
  symlink escape, workflow ordering, and real-Git reclamation/retry evidence.
- Added exact legacy-v1 registry migration for authorities created before `session_admissions` existed.

### Repair checks

- Affected implementation matrix: 383 passed.
- Concurrency conformance, including every required lifecycle-call negative mutation: 46 passed.
- Focused real worktree and broker suites: 39 + 36 passed.
- Ruff check and format check on every changed Python file: passed.
- `uv run mypy plugins/`: passed.
- `git diff --check`: passed.
