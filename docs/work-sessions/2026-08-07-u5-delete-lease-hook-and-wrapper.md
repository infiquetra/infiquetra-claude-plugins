---
title: Work session — U5 delete the lease lifecycle hook and the saga broker wrapper (#682)
date: 2026-08-07
issue: https://github.com/infiquetra/infiquetra-claude-plugins/issues/682
plan: docs/plans/2026-07-30-issue-677-lease-broker-retirement-plan.md
doc_review: docs/reviews/doc-review-issue-677-2026-07-30.md
branch: feat/682-u5-delete-lease-hook-and-wrapper
commit: 39ec7354
final_commit: 39ec7354
pull_request: https://github.com/infiquetra/infiquetra-claude-plugins/pull/701
merge_commit: 514ac02b
saga: issue-682
orchestration: inline
---

# Work session — #682 U5 delete the lease lifecycle hook and the saga broker wrapper

## What this changed, in one paragraph

U5 is the lease-broker retirement's (#677) first purely subtractive unit — and after it lands,
**runtime admission is over**: no Agent/Task spawn in saga carries any lease admission, claim, or
lifecycle record. Two whole-file deletions — `plugins/saga/hooks/lease_lifecycle_hook.py`
(92 lines) and `plugins/saga/scripts/lease_broker.py` (574 lines, the thin saga wrapper around the
fleet broker) — plus all five manifest registrations unhooked in the same commit. The precondition
was verified first (the hook was the wrapper's only importer), and the coupled surfaces moved by
construction, as in U1–U4: 13 files, +253/−1588.

## Deletion and manifest unregistration in one commit (KTD1)

The hook was registered in five event blocks — `PreToolUse` Agent|Task, `SubagentStart`,
`SubagentStop`, `PostToolUse` Agent|Task, `PostToolUseFailure`. A dangling registration is a
startup error, not a dead entry, so the file and its registrations landed in one commit.
`SubagentStart` and `PostToolUseFailure` lose the event key entirely: the lease hook was their
only registrant, and an empty event block would be a dead entry, not a retirement. The neighbours
that shared the edited blocks — team spawn residency, delegation stop audit, journal nudge — stay
armed, and the new manifest pins assert they survived. That is the guard the issue asked for:
"the remaining hooks still fire… against the manifest edit taking a neighbouring registration
with it."

## The kill switch retires with its only reader (KTD2)

`INFIQUETRA_FLEET_LEASE_ENFORCEMENT` had exactly one reader — the deleted hook; the #677 doc
review measured that in advance ("no coverage gap"). The variable stays set in the operator's
settings and is now inert. This also fires DECISIONS
`{#fence-carried-batch-renewal-671}`'s revisit-when — "the lease system's runtime admission is
retired wholesale," and U5 is that branch. Its gating question (does a 300s TTL survive the
longest real wave with renewal only at wave boundaries?) no longer needs an answer: enforcement is
not being restored; the batch-renewal heartbeat debt dies with the broker itself in U7, whose
re-add guard pins the absence.

## U4's revisit-when fires: the ritual keeps its frozen-contract calls (KTD3)

U4 KTD3 said the retired reserve/attest/release/renew calls *can* leave the `/work` ritual once
the hook is gone. Judgment: they STAY, prose re-keyed — attest still genuinely rejects a
malformed contract before launch, and deleting the commands would ripple into
`workflow_emitter.py` and `execution_spec.py`'s lease producer, the exact coupling U4 measured
and deferred; retiring the frozen contract itself is a separate decision no unit carries. What
DID go is the `configure-session`/`clear-session` admission-pinning block: it called the deleted
wrapper, and its mechanism (an admission snapshot for hooks to read) has no reader left. R11
allows no lying window — no instruction to run a deleted script survives.

## Conformance flips to ABSENCE (KTD4)

`EXPECTED_LEASE_CALLS` retired with the wrapper; the four hook adapter entry points and both
deleted file paths are pinned absent across all saga sources; the manifest presence asserts
became a per-event absence sweep. The spawn-site inventory rows carry
`retired:broker-free-(#677/U5)` — including the team-execution row's reserve/bind cells, which
documented the saga hooks firing on team-execution's spawns (deleted for ALL spawns by U5) even
though `lease_protocol.py` itself is U6's; that row's renewal/release cells stay `lease_protocol`
until U6. The `expiry-fence:no-cooperative-boundary` posture retired with the last cell that used
it, and the operator inspection/recovery section became a retirement note — no successor
mechanism; lease admission, claim, and recovery are gone, not rehomed.

## The issue's "no version bump" line is a decomposition-era artifact (KTD5)

Issue #682 says "No plugin version bump in this unit. All three release surfaces move together
in U7" — written 2026-07-30, before the #429 per-PR release-surface diff guard became the
operating rule. Deleting two plugin files and a manifest registration is exactly the non-doc
change the guard requires a bump for, so saga moved 0.129.0 → 0.130.0 as U1–U4 did; U7 still owns
the three-plugin sweep and the team-execution 3.0.0 breaking bump (R8). Related: the issue's
zero-match acceptance grep cannot be literal over a plugin tree — the CHANGELOG's historical
entries legitimately name what earlier versions shipped — recorded in LEARNINGS
`{#acceptance-greps-must-exclude-the-historical-record-682}`.

## Files modified

| File | Change |
|---|---|
| `plugins/saga/hooks/lease_lifecycle_hook.py` | Deleted whole (92 lines) |
| `plugins/saga/scripts/lease_broker.py` | Deleted whole (574 lines) |
| `plugins/saga/hooks/hooks.json` | Five lease registrations removed; `SubagentStart`/`PostToolUseFailure` keys gone entirely; neighbours untouched |
| `tests/test_saga_hooks.py` | Rewritten onto the surviving hooks (1070 → 350 lines): 33 lease test items retired; five team teardown tests kept as the surviving-hooks guard; new lease-retirement manifest pins |
| `tests/test_saga_plugin.py` | Packaging test flipped to absence; two `configure-session`/`clear-session` ritual pins dropped; version pin 0.130.0 |
| `tests/test_concurrency_conformance.py` | `EXPECTED_LEASE_CALLS` retired; file+entry-point absence pins; manifest absence sweep; four inventory rows re-keyed |
| `plugins/saga/skills/work/SKILL.md` | Admission-pinning block deleted; attest prose re-keyed post-deletion (KTD3 revisit) |
| `plugins/saga/references/concurrency-spawn-sites.md` | Four rows re-keyed; U5 re-key paragraph; operator section retired; expiry-fence posture noted retired |
| `docs/engineering-journal/DECISIONS.md` | `{#u5-deletes-the-lease-lifecycle-hook-and-the-saga-wrapper-682}` KTD1–KTD5 |
| `docs/engineering-journal/LEARNINGS.md` | `{#acceptance-greps-must-exclude-the-historical-record-682}` |
| Release surfaces | saga 0.129.0 → 0.130.0 (plugin.json, CHANGELOG, marketplace.json via `scripts/sync_marketplace.py`, version-pin test) under the #429 diff guard |

## Deliberately not done

- **`plugins/fleet-core/` untouched.** The fleet broker itself is U7's payload (10,203 lines).
- **`plugins/team-execution/` untouched.** `lease_protocol.py` and the liveness decoupling are U6's.
- **The frozen-contract ritual calls not deleted.** Kept per KTD3; retiring the contract itself is a separate decision.
- **No 3.0.0 breaking bump.** Remains U6/U7's per the plan and R8.
- **`~/.claude/settings.json` kill-switch value not removed.** It is operator config outside the repo, now inert.

## Checks run

| Gate | Result |
|---|---|
| Baseline `uv run python -m pytest -q` at 2316c0b6 | 5498 passed, 1 skipped (branch point) |
| Full suite on branch | **5466 passed, 1 skipped, 0 failed** |
| Acceptance grep `lease_lifecycle_hook\|lease_broker` on `plugins/saga/` | zero live matches — 13 hits all in CHANGELOG history (exempt class, KTD5) |
| Sentinel `tests/test_agy_run_lease.py` | 8 passed, unmodified |
| `uv run ruff check . && uv run ruff format --check .` | clean (432 files) |
| `uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` | clean (267 files) |
| `uv run bandit -ll` | no new findings (unit adds no scannable Python) |
| `python3 scripts/lint_journal_order.py` | 0 violations |
| `python3 scripts/check_release_surface_parity.py` | all plugins in parity |
| `python3 tools/release_surface_diff_guard.py --base-ref 2316c0b6` | all changed plugins bumped |

## Collected-count delta

Branch-point baseline: 5499 collected (5498 passed + 1 skipped). U5 retires thirty-three lease
lifecycle/adapter test items — admission, capacity, claim ordering, kill switch, isolation
threading, doctor/repair CLI: broker concepts with no broker-free successor — and adds one
absence pin (the manifest-retirement test replaces its presence predecessor one-for-one):
5467 collected (5466 passed + 1 skipped).

## Surprise during execution

1. **The acceptance grep is self-falsifying over a plugin tree.** The CHANGELOG inside
   `plugins/saga/` legitimately names the deleted files in its historical entries — U4 dodged
   this only because its grep was scoped to one file. LEARNINGS entry.
2. **The issue's no-bump instruction predated the diff guard it would fail.** Decomposition-era
   guidance vs the operating rule; recorded as KTD5 rather than silently obeyed or silently
   ignored.
3. **A kept test failed on first run — transcription, not behavior.** The rewrite dropped an
   `f["event"]` into `f["team_run_id"]`; a byte-diff of the kept section against git caught the
   remaining paraphrase ("acts on (#677/U2)" — original wording restored).

## Next step

Campaign #677 continues with U6 (#683): unwind team-execution's `lease_protocol.py` (whole-file
deletion candidate), decouple `liveness_protocol.py`/`liveness_engine.py`/`liveness_events.py`
under the R4a one-commit rename, own the eviction-gate story per QUEUED
`{#teardown-eviction-gate-retired-needs-u6-story}`, and carry the team-execution 3.0.0 breaking
bump (R8).
