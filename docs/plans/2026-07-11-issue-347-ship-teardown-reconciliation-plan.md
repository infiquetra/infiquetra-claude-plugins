---
title: "Issue #347: ship ends in teardown — opened-resource manifest, closing-count reconciliation, immutable ship receipt, idle worktree reclamation"
type: feat
status: active
date: 2026-07-11
origin: docs/plans/2026-07-03-plugin-fleet-grounding-brief.md
---

# Issue #347: ship ends in teardown — opened-resource manifest, closing-count reconciliation, immutable ship receipt, idle worktree reclamation

## Summary

Make teardown the ship ceremony's terminal gate: an opened-resource manifest registers every
resource the ceremony opens at open time, a new terminal `teardown` transition refuses to declare the
ceremony done while the manifest's reality-checked closing count is non-zero, an immutable
`ship_receipt.py` receipt is minted only at zero, and a certificate-gated `reclaim` subcommand removes
merged-branch worktrees (on demand and idle-triggered) while leaving unmerged ones untouched.

## Problem Frame

`ship_ceremony.py`'s transition table ends at `branch_delete` — `next_transition` returns `None` after
it (`plugins/saga/scripts/ship_ceremony.py:145-163`), so "done" is declared with zero reclamation.
The disease is live in this repo right now: `git worktree list` shows **17 worktrees**, of which 11
belong to the already-completed external-engine-offload session and 4 are stale agent worktrees under
`.claude/worktrees/` — none registered in any teardown accounting. The grounding brief documented the
same state at 15 worktrees (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:86-88`). Issue #347
folds four ideation facets (G-hybrids-3, T7-F5-2, T7-F4-7, T7-F2-2) into one terminal-gate primitive.

## Requirements

Issue #347's R1-R7 carry forward verbatim as the contract; restated here with plan-local anchors plus
the release-surface requirement.

- R1. An opened-resource manifest primitive registers every resource the ship/`/work`/`/outcome`
  cleanup path opens — branch, worktree, background session, scratch directory, draft PR — at the
  moment each is opened (register-on-open), mirroring `outcome_worktrees.register()`
  (`plugins/saga/scripts/outcome_worktrees.py:141`).
- R2. The manifest exposes a derived, on-read closing count (registered-but-not-yet-closed entries),
  computed by cross-checking the manifest against reality the way `harvest_worktrees()` cross-checks
  the registry against git (`plugins/saga/scripts/outcome_worktrees.py:297`) — never a cached field.
- R3. The ceremony's terminal "declare done" transition is gated on the closing count: it refuses
  while the count is non-zero, naming each open entry (worktree path, branch name, session id), not a
  bare boolean. HALT-not-degrade: the refusal raises before the `saga.py save`, so the ledger is
  provably unadvanced (the same proof shape as the #526 operator gate and #346 hazard gate).
- R4. `ship_receipt.py` mints an immutable receipt only once the closing count reaches zero. The
  receipt records what was opened and what was closed, is written exactly once, and is never mutated —
  a later discrepancy is a flagged anomaly, never an edit.
- R5. The reclamation-verify step re-checks reality before trusting the manifest's own closed claims:
  an entry marked closed whose resource still exists on disk is flagged as a discrepancy and counts as
  open (mirrors `reap_worktree()`'s keep-the-entry-on-failure discipline,
  `plugins/saga/scripts/outcome_worktrees.py:266-268`).
- R6. A `reclaim` subcommand reuses `outcome_worktrees` teardown (`reap_worktree` /
  `harvest_worktrees` semantics) to remove merged-branch worktrees while leaving unmerged-branch
  worktrees untouched, gated by the fleet's `reversibility_certificate.authorize_write` authority.
- R7. `reclaim` is invocable on demand and idle-triggered (no fresh manifest activity past a bound),
  so the stale-worktree failure mode cannot silently recur.
- R8. Release surfaces move in the same PR: `plugins/saga/.claude-plugin/plugin.json` → 0.78.0,
  `.claude-plugin/marketplace.json` saga entry, `plugins/saga/CHANGELOG.md` dated entry, and any
  version/metadata drift-guard tests.

## Key Technical Decisions

KTD1 — Two new modules, `ship_teardown.py` (manifest + closing count + reconcile + reclaim) and
`ship_receipt.py` (immutable writer/reader), with `ship_ceremony.py` staying a thin orchestrator:
mirrors the #346 module-per-concern layering (`ceremony_hazards.py` / `merge_watcher.py` /
`ship_undo.py`), keeps each module independently testable, and honors the issue's explicit
`ship_receipt.py` naming. Rejected: folding everything into `ship_ceremony.py` (already 842 lines;
would tangle gate logic with orchestration).

KTD2 — The manifest is a per-saga sidecar `.claude/saga/sagas/<saga_id>/opened_resources.json` with
the #346-hardened file discipline (saga-id traversal guard, wrapped `JSONDecodeError`, atomic
tmp-then-`os.replace` writes), shaped `{resource_id -> entry}` where an entry carries `kind`
(`branch|worktree|background_session|scratch|draft_pr`), `ref` (branch name / path / PR number /
session id), `opened_at`, `opened_by` (transition or call site), `closed_at` ("" while open), and
`close_evidence`. Rationale: `merge_expectation.json` and `rollback_manifest.json` already live there
per saga — one sidecar home, one hardening pattern. Rejected: extending the outcome store's
`worktrees.json` (outcome-scoped, wrong ownership axis for a per-saga ceremony).

KTD3 — The terminal transition is named `teardown`, appended after `branch_delete` in `TRANSITIONS`,
tier `REVERSIBLE`: appending makes it structurally non-skippable (AC6 — `next_transition` refuses to
report the ceremony complete until it has run, and there is no configuration bypass), and reversible
tier is honest because teardown only closes resources whose removal is reversible (merged worktrees,
scratch, already-merged draft PRs) and HALTs on anything else. Refusal raises `TeardownBlockedError`
before dispatch is recorded. Compatibility note: sagas already sitting at `branch_delete` (e.g.
issue-346) regain exactly one pending transition — "already shipped" becomes "teardown pending" —
which is desirable (old ceremonies get the gate) and is covered by an explicit test.

KTD4 — Closing count is derived on read AND reality-probed per kind (R2 + R5 in one pass): worktree →
path present per git; branch → `git rev-parse` resolves; scratch → directory exists; draft_pr →
`gh pr view` state; background_session → no liveness oracle exists, so a session entry closes only via
explicit `close` with `close_evidence` and an open one always blocks. An entry *marked closed* whose
probe says the resource still exists is a **discrepancy**: it counts as open and is named in the HALT
output (never silently trusted). Rejected: trusting `closed_at` timestamps (exactly the "green-looking
exit" the issue exists to kill).

KTD5 — Receipt immutability is mechanical, not conventional: exclusive-create (`O_CREAT|O_EXCL`) of
`.claude/saga/sagas/<saga_id>/ship_receipt.json` followed by `chmod 0444`; a second mint raises
`ReceiptExistsError`; the reader validates schema and never writes. Rejected: content-hash chains
(over-engineering for a single-writer local sidecar — write-once + read-only bit gives the same
tamper-evidence for this threat model).

KTD6 — `reclaim` sweeps `git worktree list --porcelain` (every linked worktree except the primary and
the one it runs in), not just the outcome registry: today's 17 stale worktrees are **unregistered**, so
a registry-only reclaim cannot satisfy R7. Merged-ness is decided by
`git merge-base --is-ancestor <worktree-head> <main>` (covers named branches and detached HEADs);
a worktree whose head is not an ancestor of main, or with uncommitted changes, is left untouched and
reported. Worktrees that ARE in `.saga-worktrees/`'s registry additionally route through
`outcome_worktrees.reap_worktree` so registry accounting stays honest (R6's reuse clause).

KTD7 — The reversibility gate extends `reversibility_certificate._REGISTRY` with a new
`OpKind.WORKTREE_RECLAIM_MERGED` (`tier=REVERSIBLE`, inverse descriptor: re-create via
`git worktree add` from the surviving merged branch/main); `reclaim` calls `authorize_write` per
removal and proceeds only on `AUTHORIZED`. Everything not enumerated keeps the default-GATE verdict.
Rationale: the issue mandates "the fleet's existing reversibility-verdict convention", and
`board_progression.py:127` establishes routing every op kind through `authorize_write` as the pattern.

KTD8 — Idle trigger is a `reclaim --if-idle <duration>` flag plus one additive `hooks.json`
SessionStart entry invoking `reclaim --if-idle 24h --quiet`: the flag no-ops (exit 0, "not idle")
while the newest mtime among the saga sidecars / worktree registry is younger than the bound, **and
applies the same bound per candidate worktree** — a worktree with any activity newer than the bound
(top-level or `.git` gitdir mtime) is skipped even when merged and clean, because a sibling session
sitting clean on a just-merged head is otherwise reclaimable while still alive (the merged+clean
tests pass but its cwd would vanish). On-demand `reclaim` (operator-invoked) skips only dirty and
unmerged worktrees and reports what it removed. Safety by construction: the hook path can only ever
remove merged-branch, clean, *cold* worktrees under an AUTHORIZED certificate, and repo LEARNINGS
flag hook-timing races, so the hook is non-blocking and quiet. Rejected: a cron/daemon (new
infrastructure for a problem a session-start nudge solves).

KTD9 — Register-on-open wiring is enumerated, not aspirational. Wired in code this PR: `start()`
registers the pushed branch + draft PR; `_do_open_pr` registers the PR when it creates one;
`_do_merge` closes the draft_pr entry (evidence: merge sha); `_do_branch_delete` closes the branch
entry (evidence: deleted head sha). Worktrees under `.saga-worktrees/` stay accounted by
`outcome_worktrees.register()` (the pattern R1 cites) and are swept by `reclaim`; background sessions
and scratch dirs register via the `ship_teardown.py register/close` CLI (the hook point skills call at
spawn — automatic spawn-site wiring beyond the ceremony is deferred follow-up). One owner per resource
class; no double accounting.

## Implementation Units

### U1. `ship_teardown.py` — opened-resource manifest + reality-checked closing count

**Goal:** The manifest primitive: register/close/read plus a `reconcile` pass that derives the closing
count by probing reality per kind and flags closed-but-alive discrepancies.

**Requirements:** R1, R2, R5.

**Dependencies:** none.

**Files:** `plugins/saga/scripts/ship_teardown.py` (new);
`tests/test_ship_teardown_reconciliation.py` (new).

**Approach:** Module-level functions taking `repo_root` / injectable `runner` (house testability
pattern). `manifest_path(saga_id)` under `.claude/saga/sagas/<saga_id>/opened_resources.json` with the
KTD2 schema and hardening (saga-id validation, atomic writes, wrapped decode errors). `register()` is
idempotent per `resource_id` (re-register refreshes `opened_at` only if still open); `close()` records
`closed_at` + `close_evidence` and refuses on an unknown id (fail-loud). `reconcile(saga_id, ...)`
returns a report object: per-entry status (`open` / `closed-verified` / `discrepancy`), the derived
closing count (open + discrepancy), and human-readable lines naming each blocker. A `--dry-run`-style
read-only CLI verb `reconcile` prints `CLEAN` or `HALT` + blockers and never mutates (AC2's dry-run
artifact).

**Patterns to follow:** `plugins/saga/scripts/merge_watcher.py` (sidecar path validation, atomic
`_write_sidecar`, wrapped `json.JSONDecodeError`); `plugins/saga/scripts/outcome_worktrees.py:162-176`
(`live_worktrees` — existence from git, not the registry).

**Test scenarios** (in `tests/test_ship_teardown_reconciliation.py`, named
`test_AC_<n>_<scenario>` per the issue's naming pattern):

- Happy path: register branch + worktree + scratch, close all with evidence, `reconcile` reports
  closing count 0 and `CLEAN`.
- AC1 seed shape: two orphan worktree entries + one open background_session entry → `reconcile`
  reports count 3 and names all three (`test_AC_1_blocks_on_nonzero_closing_count` asserts the gate
  end-to-end in U4; the manifest-level half lands here).
- AC4: entry marked closed whose worktree path still exists on disk → `discrepancy`, counts open,
  named in output (`test_AC_4_flags_surviving_worktree_despite_claim`).
- Edge: empty/absent manifest → count 0 (a ceremony that opened nothing may complete); corrupt JSON →
  wrapped, loud error; traversal saga_id (`../evil`) → rejected; `close()` on unknown id → raises.
- Atomicity: interrupted write leaves either old or new manifest, never a torn file (tmp+replace
  probe, mirroring `tests/test_merge_watcher.py`'s atomic-write oracle).

**Verification:** manifest section of the new test file green; `reconcile` CLI prints HALT with named
blockers against a seeded sidecar and CLEAN against a fully-closed one.

### U2. `ship_receipt.py` — immutable receipt writer/reader

**Goal:** Write-once ship receipt minted from a zero-count reconcile report; reader validates and
never writes.

**Requirements:** R4.

**Dependencies:** U1 (receipt content embeds the reconcile report).

**Files:** `plugins/saga/scripts/ship_receipt.py` (new); `tests/test_ship_teardown_reconciliation.py`.

**Approach:** `mint(saga_id, report, ceremony_summary, ...)` refuses (`TeardownBlockedError` re-raise
shape) if the report's closing count is non-zero; writes
`.claude/saga/sagas/<saga_id>/ship_receipt.json` via `os.open(..., O_CREAT|O_EXCL)` then
`chmod 0444` (KTD5); a second mint raises `ReceiptExistsError`. Receipt fields: `saga_id`, `minted_at`,
`opened` (the full manifest entries), `closed` (per-entry close evidence + verification result),
`ceremony` (pr ref, merge sha, branch, final transition). `read()` parses + schema-validates;
`read()` on a receipt whose recorded entries contradict a fresh reality probe surfaces a named anomaly
(it never edits the receipt).

**Patterns to follow:** `plugins/saga/scripts/ship_undo.py` (sidecar hardening, named refusals with
`.remedy` text folded into the message).

**Test scenarios:**

- AC3 (`test_AC_3_immutable_receipt_recorded`): full close-out → mint succeeds; receipt records every
  opened resource and its closed state; a second `mint` raises; an in-place write attempt via the
  writer API raises rather than silently overwriting.
- Error paths: mint against non-zero count → refuses, **no file created**; corrupt receipt on read →
  loud wrapped error; missing receipt on read → distinct not-minted error.
- Edge: receipt for a ceremony that opened zero resources is still valid (empty `opened`, count 0).

**Verification:** receipt section green; on-disk receipt file is mode 0444 and survives a re-mint
attempt unchanged.

### U3. `reclaim` — certificate-gated merged-worktree reclamation, on-demand + idle

**Goal:** The `reclaim` subcommand: sweep all linked worktrees, remove merged-branch ones under an
AUTHORIZED certificate, leave unmerged ones untouched, support `--if-idle`.

**Requirements:** R6, R7.

**Dependencies:** U1 (lives in `ship_teardown.py`'s CLI; reconcile output feeds the idle check).

**Files:** `plugins/saga/scripts/ship_teardown.py`;
`plugins/saga/scripts/reversibility_certificate.py` (additive `OpKind.WORKTREE_RECLAIM_MERGED` +
`OpFacts` registry entry); `plugins/saga/hooks/hooks.json` (one additive SessionStart entry);
`tests/test_ship_teardown_reconciliation.py`; `tests/test_reversibility_certificate.py` (its
`test_every_reversible_op_kind_has_registered_inverse` iterates the registry, so the new reversible
op kind must land with its inverse descriptor — extend the suite's enumerated expectations).

**Approach:** Parse `git worktree list --porcelain` (skip the primary worktree and `os.getcwd()`'s
own); per candidate: dirty tree (`git status --porcelain` in the worktree) → skip + report;
`git merge-base --is-ancestor <head> <main-ref>` false → skip + report (unmerged, KTD6); merged →
`authorize_write(WORKTREE_RECLAIM_MERGED)` must return AUTHORIZED, then `git worktree remove` (no
`--force` — a failed removal is kept and reported, mirroring `reap_worktree`'s no-silent-leak
discipline at `plugins/saga/scripts/outcome_worktrees.py:266-268`); if the path matches a
`.saga-worktrees` registry entry, route through `outcome_worktrees.reap_worktree` instead so the
registry deregisters. `--if-idle <duration>`: newest mtime across `.claude/saga/sagas/*/` sidecars and
the worktree registry younger than the bound → exit 0 "not idle" (KTD8). Hook entry invokes
`reclaim --if-idle 24h --quiet`.

**Patterns to follow:** `plugins/saga/scripts/outcome_worktrees.py:254-272` (`reap_worktree`
keep-on-failure); `plugins/saga/scripts/board_progression.py:127` (route op kinds through
`authorize_write`); `plugins/saga/scripts/ship_undo.py` (`--` argv separators where git accepts them —
scratchpad-verified set from #346).

**Test scenarios** (real-git fixtures, reusing the bare-origin + clone rig shape from
`tests/test_ship_undo.py`):

- AC5 (`test_AC_5_reclaim_merged_only`): fixture repo with one merged-branch worktree and one
  unmerged-branch worktree → reclaim removes the merged one, leaves the unmerged one, report names
  both outcomes.
- Certificate: monkeypatched `authorize_write` returning GATE → reclaim removes nothing and says why;
  registry keeps default-GATE for unenumerated ops (drift-guard).
- Dirty worktree with a merged branch → skipped + reported (never removes uncommitted work).
- Registered `.saga-worktrees` worktree → removal goes through `reap_worktree` and the registry entry
  is deregistered; a failed removal keeps the entry.
- `--if-idle`: fresh sidecar mtime → no-op exit 0; aged fixture → proceeds; a merged+clean
  candidate worktree with recent activity (mtime within the bound) is skipped in idle mode (the
  sibling-session guard, KTD8) while an aged one is removed. Detached-HEAD worktree whose commit is
  an ancestor of main → treated as merged.
- Regression: existing `tests/test_outcome_worktrees.py` suite stays green (reuse, not
  modification).

**Verification:** AC5 test green; manual spot-check afterward (`git worktree list` before/after
against this repo's live stale set) is listed in the issue's Verification section and belongs to
`/work`'s session summary, not CI.

### U4. Ceremony wiring — terminal `teardown` transition, register-on-open call sites, receipt mint

**Goal:** `teardown` becomes the ceremony's non-skippable terminal transition: reconcile → HALT with
named blockers, or mint the receipt and declare done; ceremony call sites register/close manifest
entries.

**Requirements:** R1 (wiring), R3, R4 (mint call), R8's behavior surface.

**Dependencies:** U1, U2, U3.

**Files:** `plugins/saga/scripts/ship_ceremony.py`; `plugins/saga/scripts/ship_undo.py` (teardown
entry handled as forward-only no-op in undo); `tests/test_ship_teardown_reconciliation.py`;
`tests/test_ship_ceremony.py` (transition-table assertions that currently end at `branch_delete`).

**Approach:** Append `"teardown"` to `TRANSITIONS` + `TRANSITION_TIERS` (tier REVERSIBLE, KTD3). New
`_do_teardown` in `_RUNNERS`: run U1's reconcile with reality probes; attempt authorized closes for
still-open ceremony-owned entries (merged worktrees via U3's single-worktree path, scratch removal);
re-reconcile; non-zero count → raise `TeardownBlockedError` naming every blocker **before**
`ship_undo.append_entry` and the `saga.py save` (ledger provably unadvanced, the `run()` house shape);
zero → `ship_receipt.mint(...)` and return receipt path in `extra`. Register-on-open wiring per KTD9:
`start()` registers branch + draft PR after its push/create; `_do_open_pr` registers the PR it
creates; `_do_merge` closes the draft_pr entry; `_do_branch_delete` closes the branch entry.
`ship_undo`: add a `teardown` no-op handler (receipt is forward-only truth; undo must not crash on the
new transition name).

**Patterns to follow:** `plugins/saga/scripts/ship_ceremony.py:501-614` (`run()`'s
gate-before-dispatch-before-save layering and KTD2 refusal shape);
`plugins/saga/scripts/ship_ceremony.py:614-695` (`start()`'s dual record sites note).

**Test scenarios** (extend the module fakes in `tests/test_ship_ceremony.py` style — FakeGh/FakeRunner
rigs stay in their home files; teardown-specific oracles in the new file):

- AC1 (`test_AC_1_blocks_on_nonzero_closing_count`): seed two orphan worktrees + one open
  background_session, run the `teardown` transition → refuses, names the three entries, saga
  `ceremony_transition` unchanged, no receipt file.
- AC2 (`test_AC_2_dry_run_halt_on_surviving_worktree`): `reconcile` dry-run against a seeded
  surviving-worktree scenario prints `HALT`, mints nothing.
- AC6 (`test_AC_6_terminal_transition_not_skippable`): `TRANSITIONS[-1] == "teardown"`;
  `next_transition("branch_delete") == "teardown"`; a seeded partial-failure path (remote branch
  delete failed — the `check=False` leg of `_do_branch_delete`) still reaches `teardown`, which
  reconciles and reaches an explicit terminal state (HALT or receipt); no flag or config reaches
  "already shipped" without a recorded `teardown`.
- Happy path: fully-closed manifest → `run` executes teardown, mints receipt, saga records
  `ceremony_transition=teardown`, subsequent `run` says "already shipped".
- Compat: a saga whose last recorded transition is `branch_delete` (pre-0.78.0 ceremony) reports
  `teardown` as next rather than "already shipped" (KTD3's note, asserted).
- Undo: rollback manifest containing a `teardown` entry → `ship --undo` skips it as forward-only
  no-op, never crashes.
- Open-PR/merge/branch-delete register/close wiring: each call site leaves the expected manifest
  entry state (FakeRunner-driven, no live gh).

**Verification:** all six issue AC `-k` selectors pass in
`tests/test_ship_teardown_reconciliation.py`; existing `tests/test_ship_ceremony.py`,
`tests/test_ship_undo.py`, `tests/test_merge_watcher.py`, `tests/test_ceremony_hazards.py` untouched
suites stay green.

### U5. Release surfaces + journal

**Goal:** Installed-plugin metadata tells the same story as the diff, in the same PR.

**Requirements:** R8.

**Dependencies:** U1-U4 (describes what shipped).

**Files:** `plugins/saga/.claude-plugin/plugin.json` (0.77.0 → 0.78.0);
`.claude-plugin/marketplace.json`; `plugins/saga/CHANGELOG.md`;
`docs/engineering-journal/DECISIONS.md` (KTD record for this plan);
version/metadata drift-guard tests under `tests/` (confirm which assert the saga version/file set and
update).

**Approach:** Follow the 0.77.0 CHANGELOG entry format (feature bullets per module + gate
description). DECISIONS entry records KTD3 (terminal-transition compat semantics), KTD6 (porcelain
sweep over registry-only), and KTD7 (certificate extension) with rejected alternatives and a
revisit-when. LEARNINGS only if implementation surfaces a non-obvious mechanism (per repo CLAUDE.md,
same-commit capture).

**Test expectation:** none — metadata/docs unit; the drift-guard tests it updates are the check.

**Verification:** `uv run pytest` drift guards green against the bumped version; CHANGELOG top entry
describes manifest, gate, receipt, reclaim.

## Scope Boundaries

**In scope:** the manifest primitive (register-on-open for branch, worktree, background session,
scratch, draft PR), the closing-count gate as the ceremony's terminal `teardown` transition, the
immutable receipt, the certificate-gated `reclaim` subcommand with `--if-idle` + one SessionStart hook
entry, ceremony call-site wiring (KTD9's enumerated set), release surfaces.

**Out of scope (issue non-goals, carried forward):** rebuilding `ship_ceremony.py`'s state machine or
transition table beyond appending the terminal gate; `team-execution`'s Step B8 teardown contract, TTL
reaper, and idle-eviction (theme T6, separate issue); the warm-pool residency model
(`{#worker-cache-scheduling}`); deploy/canary mutation; backfilling the primitive onto other repos.

**Deferred to Follow-Up Work:** automatic register-on-spawn wiring for background sessions and scratch
dirs at their (skill-level) spawn sites beyond the `ship_teardown.py register` CLI hook point (KTD9);
any richer idle scheduling than the SessionStart `--if-idle` nudge.

## Risk Analysis & Mitigation

- **The hook removes something someone wanted** — bounded by construction: merged-branch,
  clean-tree, **cold** (no activity within the idle bound), certificate-AUTHORIZED worktrees only;
  dirty, unmerged, or recently-active is always skipped and reported (KTD6/KTD8). Worst case is
  re-running `git worktree add` against a branch still present on origin.
- **Compat: pre-0.78.0 completed ceremonies regain a pending transition** — intended (they get the
  gate); asserted by a dedicated test; CHANGELOG calls it out so an operator seeing "teardown pending"
  on an old saga isn't surprised.
- **`run()` teardown blocks forever on an unclosable entry (e.g. an orphaned session id)** — the HALT
  names the entry and `ship_teardown.py close --id ... --evidence ...` is the documented operator
  remedy; the gate is loud, not sticky-silent, and `close` requires evidence text so the override is
  auditable.
- **Test suite touching real git worktrees is slow/flaky** — reuse the #346 bare-origin fixture rig
  (proven deterministic); worktree fixtures stay in tmp_path, never the repo.

## Success Metrics

- All seven issue ACs pass via their named `-k` selectors; full CI-parity gate green (AC7).
- Post-merge manual spot-check: `reclaim` against this repo's live stale worktrees removes the
  merged ones and leaves unmerged ones untouched (issue Verification section).
