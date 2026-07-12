---
title: Content-addressed append-only evidence ledger for /qa and /code-review verdicts
type: feat
status: active
date: 2026-07-12
origin: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/
---

# Content-addressed append-only evidence ledger for /qa and /code-review verdicts

## Summary

Build `plugins/saga/scripts/evidence_ledger.py` — a content-addressed, append-only custody ledger
for verification evidence — and rewire the durable-artifact write steps of `/qa`
(`plugins/saga/skills/qa/SKILL.md` §5.1) and `/code-review`
(`plugins/saga/skills/code-review/SKILL.md` §5.3) through it, so a later PASS can never silently
overwrite an earlier FAIL. Implements infiquetra/infiquetra-claude-plugins#398, the root leaf of
outcome `evidence-integrity` (sub-396, sub-397, and sub-402 all build on this module's API).

## Problem Frame

`/qa` and `/code-review` write their durable verdicts (`docs/qa/*.md`, `docs/code-reviews/*.md`)
as bare file writes with no clobber-guard — a grounded, previously observed failure: a probe
script overwrote a FAIL evidence artifact with a later PASS
(`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:150-151`). The repo already carries the
write-safety pattern (`outcome_store._write_once` / `_atomic_write`,
`plugins/saga/scripts/outcome_store.py:195-220`), just not on the evidence path, and none of the
existing call sites append a custody trail.

## Requirements

- **R1. No clobber on re-write.** A second write under the same logical identity
  (check, reviewed SHA, attempt) is rejected; the first write is never overwritten.
- **R2. Custody chain validates end to end.** `verify_chain()` reconstructs and validates the full
  custody log, including per-entry linkage and artifact re-hash; an overwrite attempt is rejected.
- **R3. FAIL is never overwritten by a later PASS.** A PASS after a FAIL for the same
  (check, SHA) preserves the FAIL record unchanged; the latest-per-(check, SHA) reader flags the
  transition as a supersession, never a silent green.
- **R4. Pre-registered criteria are frozen at intent capture.** The pass/fail criteria block is
  written once before a run's first attempt and is byte-identical across all attempts of that run.
- **R5. Closure HALTs on tamper.** Closure-time verify re-hashes artifact bytes on disk and
  returns a typed, non-zero failure on mismatch — never a silent pass.
- **R6. Producer cannot self-certify.** A closure verification whose verifier role equals the
  entry's producer role is rejected (HALT, not flag — see KTD4).
- **R7. `/qa` §5.1 and `/code-review` §5.3 write through the ledger** instead of a bare file
  write; an end-to-end test drives each skill's documented write path and finds the artifact in
  the custody log. (`/code-review` programmatic/report-only mode is unchanged — it performs zero
  file writes by contract, so there is nothing to ledger.)
- **R8. Repo gate stays green and release surfaces ship in the same PR** — `uv run pytest`,
  `ruff format --check`, `ruff check`, `mypy plugins/ scripts/ tests/ --ignore-missing-imports`,
  plus plugin.json / marketplace.json / CHANGELOG / drift-guard tests.
- **R9. Additive only.** No change to `outcome_store` / `manifest_store` contracts or call sites;
  no backfill of prior artifacts; coverage is forward-only from merge.
- **R10. Downstream-consumable API.** Public functions (`write`, `freeze_criteria`, `latest`,
  `verify_chain`, `close_verify`) are importable with stable signatures and an open `payload`
  dict per entry — sub-396 (durable audit store), sub-397 (closure gate), and sub-402 (spend
  receipts) extend this module without schema surgery.

## Key Technical Decisions

**KTD1 — Ledger home: committed, per-saga (`docs/evidence/<saga-id>/`).** Ledger at
`docs/evidence/<saga-id>/ledger.jsonl`, criteria blocks beside it. Committed evidence follows the
repo's committed-is-canonical philosophy (R26/R27 in the outcome model): a fresh clone can verify
the custody chain, and custody is auditable in PR history. Per-saga files keep JSONL appends from
merge-conflicting across concurrent branches. Rejected: a single global ledger (routine EOF merge
conflicts) and the git-common-dir cache (machine-local — evidence dies with the machine, defeating
the issue's purpose). Operator-confirmed 2026-07-12.

**KTD2 — Identity and supersession: logical key (check_id, reviewed_sha, attempt); content
address sha256.** Writing the exact same identity twice is rejected (R1). A retry is a NEW
attempt: it appends, never mutates. The ledger auto-assigns the next attempt number for the
(check_id, reviewed_sha) group when `--attempt` is omitted; an explicitly passed attempt is
strict — colliding with an existing one rejects (R1). The reader groups by
(check_id, reviewed_sha) and reports the latest verdict WITH its predecessor list, flagging
FAIL→PASS as `superseded_fail: true` (R3). This reconciles "reject same-identity rewrites" with
"preserve fail-then-pass history" — the two acceptance criteria that look contradictory until
attempt joins the key.

**KTD3 — Custody-log integrity: per-entry hash chain.** Each JSONL entry records
`prev` = sha256 of the previous entry's canonical JSON (`sort_keys`, genesis `prev: null`).
`verify_chain()` recomputes linkage AND re-hashes each referenced artifact on disk. This detects
tampering of the log itself, not just of artifacts — git history alone cannot, since a
force-push or local edit rewrites both.

**KTD4 — Self-certification is a HALT, not a flag.** The acceptance criterion allows "rejected or
flagged"; we reject, matching the repo-wide HALT-not-degrade bias (a flagged violation in a green
run is exactly the silent-pass failure mode this issue exists to kill). Roles are plain strings
(`producer` e.g. `qa-gate` / `code-review-gate`; `verifier` e.g. `outcome-coordinator`,
`operator`); equality of role strings is the rejection test.

**KTD5 — Dual surface: argparse CLI + importable API.** The skill wire-through points are prose
steps in SKILL.md files, so the module must be invocable as
`python3 plugins/saga/scripts/evidence_ledger.py <verb>` (the established saga.py /
issue_progress.py pattern); tests and sub-397's closure gate import the functions directly.
CLI verbs: `write`, `freeze-criteria`, `latest`, `verify-chain`, `close`.

**KTD6 — Reuse `outcome_store` primitives via import; add one new append primitive.** Import
`_write_once` / `_atomic_write` **and `_safe_name`** following the explicit `manifest_store`
precedent (`plugins/saga/scripts/manifest_store.py:72-82` already leans on the sibling's private
helpers) — reuse over mirroring avoids divergence, and the issue explicitly permits internal
reuse. Every identity component that reaches a filesystem path (saga-id, check_id, reviewed SHA)
passes through the `_safe_name` traversal guard, exactly as both existing stores require. The one
genuinely new primitive is `_append_line` (O_APPEND + fsync JSONL append); artifact and criteria
files use `_write_once` semantics. No modification to `outcome_store` itself (R9).

**KTD7 — Error model: typed `EvidenceLedgerError` + non-zero CLI exit.** Mirrors
`ManifestStoreError` (a `ValueError` subclass). Every rejection path (clobber, chain break,
tamper, self-certify, double-freeze) raises typed and exits non-zero — callers never have to
parse prose to detect a HALT. A malformed or torn trailing JSONL line also HALTs verification
with the offending line number — never quarantine-and-continue: `outcome_store` quarantines
because its cache is disposable (R30/KTD15 there); this ledger is committed evidence, so a
damaged log is an integrity event, and recovery is a deliberate manual truncation.

## Implementation Units

### U1. Core ledger — content-addressed write + hash-chained custody log

**Goal:** `evidence_ledger.py` with `write()` (sha256 the artifact content, create the artifact
file write-once, append the custody entry `{seq, hash, prev, check_id, reviewed_sha, attempt,
producer, timestamp, verdict, artifact_path, payload}`) and `verify_chain()` (linkage + artifact
re-hash).

**Files:** `plugins/saga/scripts/evidence_ledger.py` (new), `tests/test_evidence_ledger.py` (new).

**Test scenarios:** `tests/test_evidence_ledger.py` — `test_evidence_ledger_no_clobber` (second
write of same identity rejected; artifact file unchanged; also: same path with different identity
rejected), `test_evidence_ledger_custody_chain_validates` (N writes → verify_chain passes;
hand-edited entry → typed failure; deleted artifact → typed failure; torn/malformed trailing
line → typed failure naming the line; traversal-shaped id, e.g. `../escape`, rejected by the
`_safe_name` guard).

**Depends on:** none.

### U2. Frozen criteria + supersession reader

**Goal:** `freeze_criteria()` — write-once criteria block per (check_id, reviewed_sha) at
`docs/evidence/<saga-id>/criteria-<check_id>-<full-40-char-sha>.json` (full SHA — no
short-SHA ambiguity in an integrity artifact), hash recorded as a `criteria` ledger entry;
attempt writes validate the frozen block exists and its hash is unchanged. `latest()` —
latest-per-(check_id, reviewed_sha) with full predecessor list and `superseded_fail` flag.

**Files:** `plugins/saga/scripts/evidence_ledger.py`, `tests/test_evidence_ledger.py`.

**Test scenarios:** `test_evidence_ledger_criteria_frozen_across_attempts` (freeze → attempt-1
FAIL → attempt-2 PASS: both attempts persisted, criteria bytes identical, second freeze rejected),
`test_evidence_ledger_fail_then_pass_supersession` (FAIL then PASS same (check, SHA): FAIL record
byte-unchanged in the JSONL, reader returns PASS with `superseded_fail: true`).

**Depends on:** U1.

### U3. Closure verify + producer/verifier role separation

**Goal:** `close_verify(verifier=...)` — run the full chain verify, re-hash every artifact, HALT
on any mismatch (R5); reject when `verifier` equals any certified entry's `producer` (R6, KTD4);
on success append a `closure` entry recording the verification. The closure entry certifies the
entries that precede it and is appended only after verification succeeds — it is never part of
its own verification scope (a later `close_verify` or `verify_chain` covers it like any entry).

**Files:** `plugins/saga/scripts/evidence_ledger.py`, `tests/test_evidence_ledger.py`.

**Test scenarios:** `test_evidence_ledger_closure_halts_on_tamper` (mutate artifact bytes after
write → close_verify returns typed non-zero failure), `test_evidence_ledger_producer_cannot_self_certify`
(close with verifier == producer role → rejected; distinct verifier → passes).

**Depends on:** U1 (chain), U2 (criteria entries participate in closure).

### U4. Wire `/qa` §5.1 and `/code-review` §5.3 through the ledger

**Goal:** Rewrite `plugins/saga/skills/qa/SKILL.md` "5.1 Write the durable artifact" and
`plugins/saga/skills/code-review/SKILL.md` "5.3 Write the durable artifact" to compose the
artifact content as today, then persist via `evidence_ledger.py write` (producer `qa-gate` /
`code-review-gate`, verdict from the gate's own derivation, reviewed SHA from the existing
capture) — plus one criteria-freeze instruction at each gate's intent-capture point: for `/qa`,
at Phase 2 entry ("Run checks per class"), freezing the check-class set Phase 1's risk
classification produced; for `/code-review`, at the end of Phase 1 ("Intent and built-vs-planned
audit"), freezing the reviewed-SHA + lens scope before the Phase 3 review fan-out.
`/code-review` programmatic mode stays untouched.

**Ledger scope when no saga exists:** both gates can run without a work-thread saga
(`/code-review` §5.4 documents the no-saga branch explicitly). The artifact must STILL go through
the ledger (R7) — the write falls back to the ledger directory
`docs/evidence/adhoc-<branch-slug>/` (branch slug from the same branch-or-pr stem the artifact
filename already uses). Only the saga *tick* is skipped in the no-saga case, never the custody
entry.

**Files:** `plugins/saga/skills/qa/SKILL.md`, `plugins/saga/skills/code-review/SKILL.md`,
`tests/test_evidence_ledger.py`.

**Test scenarios:** `test_evidence_ledger_qa_and_code_review_write_through` (drive each skill's
documented CLI invocation shape end-to-end in a tmp repo; assert the artifact lands AND its
custody entry exists with the right producer role; include the no-saga case landing in
`docs/evidence/adhoc-<branch-slug>/`). Guard: grep-level assertion that neither SKILL.md
§-section still instructs a bare write.

**Depends on:** U1–U3 (the CLI verbs it invokes).

### U5. Release surfaces + full CI gate

**Goal:** saga 0.80.0 → 0.81.0 in `plugins/saga/.claude-plugin/plugin.json`, matching
`.claude-plugin/marketplace.json` entry, `plugins/saga/CHANGELOG.md` entry describing the new
evidence-ledger write path, drift-guard tests re-run; full repo gate green (R8).

**Files:** `plugins/saga/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
`plugins/saga/CHANGELOG.md`.

**Test expectation:** none — release bookkeeping; covered by existing drift-guard tests
(version/metadata consistency) and the full-suite run.

**Depends on:** U1–U4.

## Execution prerequisites

**Pause before `/work`.** Operator condition (2026-07-12): execution is inline, but do not start
`/work` until the operator has switched the session to the issue's recommended executor tier
(Sonnet / medium). Surface this at route time; never begin implementation on the planning model.

**Branch and merge target.** Leaf work branches from `main` (e.g. `work/398-evidence-ledger`);
the PR merges to `main`. The outcome branch `outcome/evidence-integrity` holds only the spec —
the outcome coordinator harvests sub-398 completion from the merged PR.

## Scope Boundaries

Out of scope (from the issue, binding):

- No ledger coverage for other artifact-write paths (`outcome_store` leases, `manifest_store`
  manifests, `saga_spore.py`, `reversibility_certificate.py`) — mutable-by-contract, separate
  future issue.
- No UI / dashboard / browsing surface for the custody log.
- No change to `/qa` or `/code-review` verdict logic, severity model, or report format — write
  mechanism only.
- No change to `outcome_store._write_once` / `_atomic_write` themselves or their call sites.
- No retroactive re-hash or migration of pre-existing evidence artifacts — forward-only.

Deferred to follow-up work (not non-goals):

- Cross-process ledger locking. The saga flow is single-writer-per-branch; O_APPEND suffices
  today. If a future multi-writer path appears (e.g. parallel worktree gates on one saga), add a
  lock mirroring `outcome_store`'s locks_dir pattern.
- sub-396 / sub-397 / sub-402 integrations — they consume this API in their own leaves.
- Survivor JSON stamping. The issue's "Files expected to change" lists
  `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/{T11,T10,seeds}.json`, but no acceptance
  criterion requires touching them and the survivor schema carries no ship-status field
  (verified: entries hold `verdict`/`dod_sketch`, nothing stampable) — treat the listing as
  advisory issue-map metadata and confirm at `/handoff`/`/retro` whether the issue-map tooling
  stamps them.
