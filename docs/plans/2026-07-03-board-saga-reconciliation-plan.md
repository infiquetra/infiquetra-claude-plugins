---
title: Board-Saga Reconciliation on Resume — drift detection over the /outcome board-sync ledger
type: feat
status: active
date: 2026-07-03
origin: docs/brainstorms/2026-06-28-board-saga-reconciliation-requirements.md
---

# Board-Saga Reconciliation on Resume — drift detection over the /outcome board-sync ledger

## Summary

Build the reconcile-on-wake companion to #279's autonomous board-sync writer (issue #295): detect when an outside writer changed a saga-owned board field while saga was at rest, surface the divergence with a human-in-the-loop ask ({accept board, re-assert saga, hold}), and record the resolution append-only — without adding any new writer or persistence.

Detection runs automatically at the `/outcome advance --autonomous` boundary (before any board-sync write, drift-holding the affected issue's ops) and on an explicit `reconcile` verb. The baseline is #279's shipped board-sync ledger plus deterministically recomputed expected values — no #279 schema change needed.

---

## Problem Frame

#279 shipped (PR #310, 2026-06-29): `outcome_board_sync.reconcile_board` drives reversibility-authorized board writes (Status, sub-issue-close, progress comments) under `reversibility_certificate.authorize_write`, recording each success as an idempotency-key file in the board-sync ledger (`store.root/board-sync/`). What it never does is re-read the live board. Worse than #295 stated: a recorded idempotency key makes the next tick **skip** the op (`outcome_board_sync.py:318`), so an outside change is neither detected nor re-asserted — it silently persists forever.

### Verification against shipped state (issue #295 was written pre-#279-ship; 2026-07-03 audit)

| Issue #295 claim | Verified reality |
|---|---|
| Depends on #279, "plans after #279 ships" | #279 CLOSED 2026-06-29 (PR #310, saga 0.42.0) — unblocked |
| Baseline = "R19 tick records ∪ in-flight idempotency keys" (KD2) | No saga-tick write records and **no persisted in-flight keys** exist. Shipped record = board-sync ledger, one JSON per key `{key, op_kind, repo, number, target_state, ts}`, written **only on success** (`outcome_board_sync.py:360-403`) |
| "If R19's record is thinner, first task is a bounded #279 record touch" | Not needed: keys are pure functions (`reversibility_certificate.idempotency_key`) and expected values are derivable (`derive_states` + `_candidate_ops` + schema status map), so landed-but-unrecorded writes reconcile by recomputation (KTD1) |
| Trigger rides `/resume` / S-3 SessionStart path (Q1 lean) | `/resume` is contractually read-only on the world (`skills/resume/SKILL.md:336`); S-3's SessionStart hook is compact-scoped, deadline-bounded, offline. Board-sync exists only for `/outcome` stores → trigger home is the `/outcome` boundary (KTD2, operator-confirmed) |
| Saga-owned field class includes "saga-managed labels" (KD3/Q2) | The shipped writer never emits label ops (`_candidate_ops`, `outcome_board_sync.py:149-169`) — labels are certificate-authorized but unused. v1 class = what the writer writes (operator-confirmed) |
| External close is pure drift (R1.6) | Conflict the issue missed: `advance` already **harvests a closed issue as GitHub-canonical completion** for issue-contract leaves (`outcome_orchestrator.py:117-124`) — a sanctioned silent adoption. Resolution: contract-aware + `stateReason` discrimination (KTD4, operator-confirmed). `outcome_github.issue_state` reads only open/closed today |
| `sdlc_manager.py` touched "only if a read verb is missing" | No per-card Status read verb exists in mission-control (only `board view --project [--status]` column dumps) — but none is needed: `gh issue view --json projectItems` returns per-project Status directly (`{"status":{"name":"Todo"},"title":"Operations"}`, probed live 2026-07-03). U1 adds a saga-side read; mission-control is untouched |
| Code anchors `outcome.py:1065`, `outcome_github.py:170,187` | Moved: `issue_close` commentary now at `outcome.py:~1192` (prune context); `outcome_github.py` write side now at `:169-193` — cosmetic drift only |

The temporal frame (drift mostly arises while saga is at rest; earliest supported detection is the next wake), co-ownership (KD7), and HITL-now-precedence-later (KD6) all survive verification and are carried forward.

---

## Requirements

Traceable to issue #295 R1.1–R1.9 as corrected above.

- R1. Drift detection auto-runs at the top of the `advance --autonomous` board-sync block — before any board-sync write — and via an explicit `outcome.py reconcile <outcome-id>` verb. No SessionStart hook, no resident monitor, no polling. (Issue R1.1, Q1 resolved.)
- R2. The reconcile baseline is the board-sync ledger records plus reconcile-override records plus deterministically recomputed expected values. R1 persists nothing new except override records appended to the existing ledger namespace. (Issue R1.2, corrected per KTD1.)
- R3. The v1 saga-owned field class is exactly what the writer writes: board Status and issue open/closed state, plus recovery of landed-but-unrecorded writes. Detection scope is ledger-bearing issues (at least one recorded write or override). Labels and comment-deletion are excluded until the writer emits them. (Issue R1.3, Q2 resolved.)
- R4. When every in-scope field matches the baseline, reconciliation is silent — an empty drift list, no operator interruption. (Issue R1.4.)
- R5. On divergence, each drift record carries {kind, repo, issue number, op family, saga value, board value, external author when discoverable} and the offered resolutions are {accept-board, re-assert, hold}. Reconcile never force-heals and never writes against a drifted issue: the affected issue's board-sync ops are drift-held for the tick. (Issue R1.5.)
- R6. External closes are contract-aware with `stateReason`: a close that satisfies the leaf's completion contract with `state_reason == "completed"` remains the harvester's sanctioned silent path; a `not_planned` close, or a close that does not satisfy the contract, is drift. An unreadable `stateReason` degrades to contract-only semantics (today's shipped behavior). An external reopen of a saga-closed issue is drift. (Issue R1.6, KTD4.)
- R7. Operator resolutions are recorded as append-only `reconcile-override` records in the board-sync ledger namespace. A re-assert resolution re-drives the write through `reversibility_certificate.authorize_write` plus the injected `board_writer` seam — never a direct GitHub call. (Issue R1.7.)
- R8. The resolution decision routes through one replaceable policy hook — `decide(drift, *, policy=None)` returning a resolution or `None` (None = ask the operator). v1 pins the call site and signature; the precedence policy itself is deferred. (Issue R1.8, Q3 lean adopted.)
- R9. R1 adds no autonomous writer and no new board write verbs: the only board mutations are operator-chosen re-asserts through the existing writer seam. Mission-control is untouched — all new reads are `gh`-level in `outcome_github.py`. (Issue R1.9.)
- R10. Release surfaces ship in the same PR: saga's `plugin.json` and `CHANGELOG.md`, `.claude-plugin/marketplace.json`, and the version drift-guard tests tell the same story as the diff.

---

## Key Technical Decisions

- KTD1 — Reconstruct intent, don't persist it: the baseline recomputes expected board values from `derive_states` + `_candidate_ops` + the schema status map, and recomputes idempotency keys via `reversibility_certificate.idempotency_key`, instead of adding an intent ledger to #279's writer. Keys and values are pure functions of observable state, so the success-only ledger plus recomputation covers the landed-but-unrecorded case (`{status:"error", may_reapply:true}` path) with zero changes to the shipped, scope-locked writer. Rejected: two-phase intent/commit ledger for board-sync (exists for dispatch in `outcome_store`, but duplicates what recomputation gives for free).
- KTD2 — The trigger home is `/outcome`, not `/resume` or hooks: the ledger lives in the outcome store, `/resume` is read-only on the world by contract, and SessionStart hooks are deadline-bounded and must stay offline (network board fetches don't belong there). Auto-detection at `advance --autonomous` plus an explicit `reconcile` verb gives "automatic-but-silent-unless-divergent" without a new trigger surface. Rejected: the issue's suggested `skills/resume/SKILL.md` wiring and any SessionStart hook.
- KTD3 — Drift-hold, not gate-all: a detected drift withholds only the affected issue's board-sync candidate ops for that tick (a `hold_issues` set threaded into `reconcile_board`, recorded per-op as `{status:"drift-hold"}`); other leaves' ops proceed. Rejected: halting the whole autonomous sync on any drift — punishes unrelated leaves and stalls the outcome.
- KTD4 — Contract-aware + `stateReason` close semantics (operator-selected): sanctioned completion (contract satisfied, `completed`) stays silent and the harvester path is untouched; `not_planned` or contract-unsatisfied closes are drift; unreadable `stateReason` degrades to contract-only, i.e. exactly today's behavior. Rejected: treating all external closes as drift (fights the shipped harvester and prompts on every legitimately completed non-code leaf).
- KTD5 — Resolutions are append-only override records in the same ledger namespace: baseline-on-read takes the latest of {ledger record, override record} per op family by `ts`, so accept-board permanently silences that exact board value without mutating history, and re-assert records the re-driven value. Hold records nothing — the drift resurfaces on the next detection, consistent with the outcome engine's level-triggered philosophy (R29).
- KTD6 — Detection scope is ledger-bearing issues: reconcile contradicts *recorded* writes; a pre-write leaf has nothing recorded to contradict, and Status is written at ready/dispatch, so mid-flight external closes are covered in practice. Rejected: live-reading every leaf's issue every tick (N extra `gh` calls for a window the harvester already partially observes).
- KTD7 (revised at doc-review, 2026-07-03) — Board Status is read via `gh issue view --json projectItems` in `outcome_github.py`, not a new mission-control verb: the live probe showed `projectItems` carries per-project `{status: {name}, title}` in one plain `gh` call, so the original premise (a GraphQL read verb was the only path) is falsified. The project is selected by case-insensitive title↔slug match ("Operations" ↔ `operations`); no matching item degrades to unreadable. `outcome_reconcile` still consumes it through an injected `board_reader` callable — the testability seam is unchanged. Rejected: a mission-control `flow get-field` GraphQL verb (generic and symmetric with `set-field`, but a second plugin's release surface + first-ever flow-verb tests for a capability one `gh issue view` field already provides; revisit if a generic field read is ever needed beyond Status).

---

## High-Level Technical Design

Detection is a pure classification over three per-issue views; only re-assert ever writes to GitHub.

```
advance --autonomous            outcome.py reconcile <id>
        |                                  |
        v                                  v
outcome_reconcile.detect(spec, store, board_reader, issue_reader)
   |  scope: issues with >=1 ledger/override record (KTD6)
   |  per issue, three views:
   |    asserted = latest(ledger record, override record) per op family (KTD5)
   |    expected = derive_states -> _candidate_ops -> schema status map (KTD1)
   |    live     = board_reader (Status) + issue_reader (state, stateReason, closedBy)
   |
   +-- live == asserted (and open/closed consistent)      -> silent          (R4)
   +-- live == expected, no ledger key                    -> recover record  (AE3)
   +-- live != asserted Status                            -> drift: status-drift
   +-- closed, no close key, contract+completed           -> silent (harvester's, KTD4)
   +-- closed, no close key, not_planned OR non-contract  -> drift: external-close
   +-- open, close key recorded                           -> drift: external-reopen
   |
   v
drift records -> advance: drift-hold that issue's board ops (KTD3), surface in AdvanceResult
             -> skill layer asks operator {accept-board | re-assert | hold}   (R5)
                        |
                        v
outcome_reconcile.decide(drift, policy=None) -> None = HITL   (R8 seam)
outcome_reconcile.apply_resolution(...):
   accept-board -> append reconcile-override record            (R7)
   re-assert    -> authorize_write -> board_writer -> override record (R7, R9)
   hold         -> nothing; resurfaces next detection          (KTD5)
```

Author attribution is best-effort per R5: `closedBy` is discoverable for closes; ProjectV2 exposes no per-field audit trail through the API surface used here, so status-drift records omit the author.

---

## Implementation Units

### U1. `board_status` — per-issue project-Status read (outcome_github)

One-line: a degrade-safe one-call read of an issue's board Status via `gh issue view --json projectItems` — no mission-control change, no GraphQL.

**Goal:** `outcome_github.board_status(issue_ref, *, project) -> str` returning the Status option name for the project whose title matches the slug case-insensitively ("Operations" ↔ `operations`), or `""` when unreadable/absent.

**Requirements:** R3, R9 (read-only), R10.

**Dependencies:** none.

**Files:** `plugins/saga/scripts/outcome_github.py`; `tests/test_outcome_completion.py`.

**Approach:** one `gh issue view <ref> --json projectItems` call — probed live 2026-07-03, returns `{"projectItems":[{"status":{"optionId":...,"name":"Todo"},"title":"Operations"}]}`. Select the entry whose `title.lower()` equals the project slug; return its `status.name`. Every failure (gh non-zero, malformed JSON, no matching project item, null status) degrades to `""` — mirroring `issue_state`'s never-raise contract (`outcome_github.py:79-92`).

**Patterns to follow:** `issue_state` / `merge_state` degrade-to-safe-value shape in the same file.

**Test scenarios:** (1) happy path — mocked payload with the Operations item at Status "In Progress" → `"In Progress"`. (2) multi-board membership — two project items; only the slug-matched title is read. (3) issue on no matching project → `""`. (4) gh non-zero exit / malformed JSON / `status: null` → `""`, no raise.

**Verification:** `uv run pytest tests/test_outcome_completion.py -k board_status` green; `rg -n "graphql" plugins/saga/scripts/outcome_github.py` still finds nothing (one-call read, no new API surface).

### U2. `issue_close_info` — stateReason-bearing close read (outcome_github)

One-line: a degrade-safe read returning how an issue was closed, powering KTD4's completed-vs-not_planned discrimination.

**Goal:** `outcome_github.issue_close_info(issue_ref) -> {"state": "open|closed|unknown", "state_reason": "completed|not_planned|reopened|unknown", "closed_by": "<login or empty>"}`.

**Requirements:** R5 (author), R6.

**Dependencies:** none.

**Files:** `plugins/saga/scripts/outcome_github.py`; `tests/test_outcome_completion.py`.

**Approach:** two calls, both verified live 2026-07-03. State + reason from `gh issue view <ref> --json state,stateReason` (probed: `{"state":"CLOSED","stateReason":"COMPLETED"}`; normalize to lowercase — no close-author field exists in `gh issue view`'s field list). Close author best-effort from `gh api repos/<owner/repo>/issues/<n>/events --paginate`, taking the last `"event":"closed"` entry's `actor.login` (probed: returns `{"actor":"namredips","event":"closed"}`); `--paginate` matters — issues with >30 events would otherwise miss the close. Every failure degrades to `"unknown"`/empty, mirroring `issue_state`'s never-raise contract (`outcome_github.py:79-92`). `issue_state` itself stays untouched — its existing callers (harvester barrier) keep their exact semantics.

**Patterns to follow:** `issue_state` / `merge_state` degrade-to-safe-value shape in the same file.

**Test scenarios:** (1) closed as completed with actor — full dict returned. (2) closed as not_planned — `state_reason: "not_planned"`. (3) open issue — `state: "open"`, reason empty/unknown. (4) gh non-zero exit / malformed JSON / non-dict payload — all-unknown dict, no raise.

**Verification:** `uv run pytest tests/test_outcome_completion.py -k close_info` green; `issue_state` tests unchanged and green.

### U3. `outcome_reconcile.py` — detection core

One-line: the pure classification engine — baseline from ledger + overrides + recomputed expectations, diffed against injected live reads, returning typed drift records.

**Goal:** `detect(spec, store, *, board_reader, issue_reader, project="operations", schema_path=None) -> list[dict]` implementing the HTD classification exactly; plus the `recover record` branch writing the missing ledger key for a landed-but-unrecorded write.

**Requirements:** R2, R3, R4, R5 (record shape), R6.

**Dependencies:** U1/U2 define the injected callables' return shapes (build against those dict shapes; callables are injected, so U3 is testable before U1/U2 land).

**Files:** `plugins/saga/scripts/outcome_reconcile.py` (new); `tests/test_outcome_reconcile.py` (new).

**Approach:** house pattern (pure functions over explicit values, lazy imports, no I/O at import — mirror `outcome_board_sync.py`'s header). Baseline reader walks `store.root/board-sync/` distinguishing write records from `reconcile-override` records by a `kind` field (absent = write record, for backward compatibility with #279's existing files); per (repo, number, op family) keep the latest by `ts` (KTD5). Expected values reuse `outcome_board_sync._resolve_status_map` and `_candidate_ops` — import them, do not copy. Drift record shape: `{"kind": "status-drift|external-close|external-reopen", "repo", "number", "subplot_id", "op_kind", "saga_value", "board_value", "author", "drift_id"}` where `drift_id` is a deterministic short hash of (kind, repo, number, saga_value, board_value) so the CLI can reference a drift across invocations. Recover-record branch: live Status equals derived-expected and no ledger key → write the key via `outcome_store._write_once` with a `"recovered": true` field; report it as a `{"kind": "recovered"}` informational record, not drift.

**Patterns to follow:** `outcome_board_sync.py` module structure, ledger-file conventions (`_safe_ledger_name`), and its injected-callable test style in `tests/test_outcome_board_sync.py`.

**Test scenarios** (name the test functions so issue #295's acceptance-criteria `-k` selectors stay meaningful against the convention-correct path `tests/test_outcome_reconcile.py` — the issue's `tests/test_saga_reconcile.py` is superseded by the repo's `test_outcome_*` convention: `test_silent_when_match`, `test_surfaces_divergence`, `test_scope_excludes_operator_field`, `test_external_close_surfaced`, `test_partial_failure_no_blind_spot` here; `test_reassert_via_authorize_write`, `test_no_new_writer` in U4): (1) silence — live matches asserted for Status and open/closed → empty list (issue AE-silent, `test_silent_when_match`). (2) status-drift — ledger says saga set "In Progress", live reads "Blocked" → one drift record with both values (AE4 shape). (3) recovered record (AE3) — live Status equals derived-expected, no ledger key → key file written with `recovered: true`, informational record, no drift. (4) sanctioned close — issue-contract leaf closed, `state_reason: "completed"` → silent (KTD4). (5) not_planned close → external-close drift carrying `closed_by` (AE1 shape). (6) contract-unsatisfied close — leaf whose contract a close does not satisfy (e.g. PR-contract leaf, unmerged PR) closed as completed → external-close drift. (7) unreadable stateReason (all-unknown dict) → degrades to contract-only: silent when contract-satisfying, drift otherwise. (8) external reopen — close key recorded, live open → external-reopen drift. (9) scope discipline — an issue with no ledger/override record is never read nor flagged (AE2, KTD6); assert `board_reader` was not called for it. (10) out-of-scope field — a hand-added label changes nothing (never read) — no false positive. (11) override-as-baseline — prior accept-board override for board value X; live still X → silent (no re-flag); cover both a Status override and an accepted external-close (the close stays closed, no re-ask).

**Verification:** all scenarios green offline (mock readers, `tmp_path` stores); `uv run mypy plugins/saga/scripts/outcome_reconcile.py` clean.

### U4. Resolutions + the precedence seam

One-line: apply {accept-board, re-assert, hold} through one policy hook, recording override facts append-only and re-driving writes only through the #279 seam.

**Goal:** `decide(drift, *, policy=None) -> str | None` (v1: `None` when policy is `None` — HITL); `apply_resolution(drift, resolution, *, store, board_writer, now=time.time, max_attempts=3) -> dict`.

**Requirements:** R7, R8, R9.

**Dependencies:** U3.

**Files:** `plugins/saga/scripts/outcome_reconcile.py`; `tests/test_outcome_reconcile.py`.

**Approach:** accept-board appends `{"kind": "reconcile-override", "resolution": "accept-board", "op_kind", "repo", "number", "board_value", "drift_id", "ts"}` via `_write_once` (filename from the drift_id — deterministic, so replaying the same resolution is idempotent). Re-assert: `authorize_write(op_kind)` first (GATE → refuse with a `{"status":"gated"}` result — never bypass the certificate), then the injected `board_writer` with bounded retry mirroring `reconcile_board`'s loop, then the override record with `"resolution": "re-assert"`. Hold: return a `{"status":"held"}` result, write nothing. Accept-board on a not_planned close does not mint a completion event — the result carries an advisory pointing at `/outcome prune` for the leaf (graph edits stay the operator's, R9).

**Patterns to follow:** `reconcile_board`'s bounded-retry + write-once-on-success sequence (`outcome_board_sync.py:343-418`).

**Test scenarios:** (1) accept-board writes exactly one override record; re-running the same resolution is a no-op (idempotent filename). (2) re-assert calls `authorize_write` then `board_writer` — assert with a recording fake that no direct `gh` path exists (AE4 / issue acceptance "reassert_via_authorize_write"). (3) re-assert of a gated op (e.g. a future op kind not in the registry) → `gated` result, no write, no record. (4) board_writer raises on all attempts → `failed` result, no override record (retryable). (5) hold → no ledger change; a second `detect` still reports the drift. (6) policy seam — `decide` returns `None` with no policy; a stub policy returning "accept-board" short-circuits without an ask (proves the seam is load-bearing, R8).

**Verification:** `uv run pytest tests/test_outcome_reconcile.py` green; grep proves no `subprocess`/`gh` call is introduced in `outcome_reconcile.py` (writes only via the injected seam).

### U5. Wiring — `reconcile` verb, advance auto-detect, drift-hold

One-line: surface detection at both triggers and make the writer refuse to write against a drifted issue.

**Goal:** `outcome.py reconcile <outcome-id> [--resolve <drift-id> --action accept-board|re-assert|hold]` prints detection/resolution JSON; `advance --autonomous` runs `detect` first, threads `hold_issues` into `reconcile_board`, and carries drift records in `AdvanceResult.drift`.

**Requirements:** R1, R4, R5 (drift-hold), R9.

**Dependencies:** U3, U4.

**Files:** `plugins/saga/scripts/outcome.py`; `plugins/saga/scripts/outcome_board_sync.py` (optional `hold_issues: set[tuple[str, int]]` param recording `{status:"drift-hold"}` per withheld op); `tests/test_outcome_command.py`; `tests/test_outcome_board_sync.py`.

**Approach:** default readers built beside `_default_board_writer` (`outcome.py:448`) as thin closures over U1's `board_status` and U2's `issue_close_info` — plain function calls, no subprocess needed (both live in `outcome_github`). In the autonomous block (`outcome.py:640-656`), call `detect` before `reconcile_board`; drift → hold set + `AdvanceResult.drift` (new dataclass field, default empty, serialized in `to_dict`). `reconcile` CLI subcommand loads spec/store like `resume` (`outcome.py:277`) and takes no coordinator lease: detection is read-only on GitHub, and its only local writes are recovered-record ledger files created via `outcome_store._write_once` (atomic temp + `os.link`, returns False on existing key) — a concurrent `advance` writing the same key is a benign no-op race. `--resolve` applies U4 with the production board_writer. Detection failures (network) degrade per-issue to an `{"kind":"unreadable"}` note — never wedge the tick (mirror `reconcile_board`'s fail-loud-not-fatal convention).

**Patterns to follow:** `resume`/`status` subcommand shape; the `autonomous:` block's lazy import + injected-default pattern; `AdvanceResult` serialization at `outcome.py:~430`.

**Test scenarios:** (1) `reconcile` on a store with no board-sync dir → `{"drift": []}`, exit 0, and no reader calls. (2) advance with injected fake readers reporting drift → the drifted issue's ops appear as `drift-hold` records, other issues' ops written normally (KTD3), `AdvanceResult.drift` populated. (3) advance with no drift → board-sync behavior byte-identical to today (regression guard over existing `test_outcome_board_sync` fixtures). (4) `--resolve` accept-board → override record lands; subsequent advance no longer holds that issue. (5) reader raising → per-issue `unreadable` note, tick completes, no ledger key written for that issue. (6) non-autonomous advance never calls `detect` (no network on default path).

**Verification:** `uv run pytest tests/test_outcome_command.py tests/test_outcome_board_sync.py tests/test_outcome_reconcile.py` green; a manual `outcome.py reconcile` run against a scratch outcome prints the empty-drift JSON.

### U6. Skill, references, and release surfaces

One-line: document the reconcile contract where operators and agents read it, and ship the version story in the same PR.

**Goal:** `/outcome` skill and references teach the reconcile verb, drift-hold semantics, and the HITL ask; release surfaces bump coherently (saga 0.50.0 → 0.51.0; mission-control untouched per revised KTD7).

**Requirements:** R5 (ask wording), R10.

**Dependencies:** U1–U5.

**Files:** `plugins/saga/skills/outcome/SKILL.md` (verbs table row + a "Reconcile-on-wake" subsection under autonomous board-sync, `SKILL.md:87-119`); `plugins/saga/references/outcome-spec.md` (the reconcile contract + the saga-owned field class — the issue named `execution-spec.md`, but that file documents the ExecutionSpec DSL; the outcome reference is the correct home); `plugins/saga/CHANGELOG.md`; `plugins/saga/.claude-plugin/plugin.json`; `.claude-plugin/marketplace.json`; `docs/engineering-journal/DECISIONS.md` (KTD entry recorded at plan time; flip status on ship).

**Approach:** the skill's HITL ask presents each drift as one line — `{kind} {repo}#{number}: saga={saga_value} board={board_value} (author?)` — with the three resolutions and the not_planned→prune advisory from U4. Keep the AskUserQuestion/channel-inline convention by reference to the existing skill wording, not duplicated.

**Test scenarios:** existing drift guards must pass with the new version — `tests/test_saga_plugin.py`, `tests/test_release_triad.py`, `tests/test_marketplace_hook.py`; add/extend the guard if the new verb or version is asserted anywhere. Otherwise `Test expectation: none — docs/metadata unit; behavior covered by U1–U5 tests.`

**Verification:** `uv run pytest tests/test_saga_plugin.py tests/test_release_triad.py tests/test_marketplace_hook.py` green; CHANGELOG entry names the reconcile verb, drift-hold, `board_status`, and `issue_close_info`.

---

## Scope Boundaries

**In:** detection over ledger-bearing issues at the `/outcome` boundary; HITL resolution with {accept-board, re-assert, hold}; append-only override records; the policy-hook seam; the two small read verbs; drift-hold in the writer path.

**Out (true non-goals):** any new autonomous writer (the write path stays #279's, incl. driver/adapters/idempotency/failure path); board-as-projection or saga-as-sole-writer (co-ownership stands, issue KD7); resident monitors, polling, webhooks, or SessionStart hooks; a built writer-precedence policy (seam only); PR-merge / deploy autonomy (permanently HITL, #279 R20); label and comment-deletion drift (writer never emits labels; comments are additive).

**Deferred follow-up work:** live read-before-write mid-run guarding (issue KD5's accepted v1 window); adopting U2's `issue_close_info` inside the harvester's `barrier_satisfied` so a `not_planned` close of a never-written leaf stops being invisible (today it is; KTD6 accepts this for v1); a real precedence policy behind the R8 seam ("review-agent changes to field X auto-resolve"); extending the field class when the writer starts emitting label ops.

---

## Risks & Dependencies

- `gh` field availability is verified, not assumed (2026-07-03 probes): `stateReason` and `projectItems` work in the installed gh; no close-author field exists in `gh issue view`, so `closed_by` rides the REST events endpoint with `--paginate` (>30-event issues would otherwise miss the close event). All reads degrade to unknown/empty per the `outcome_github` contract, so a future gh field change can only blank the author, never break detection.
- Detection adds per-ledger-issue network reads to `advance --autonomous`: bounded by KTD6 scope (ledger-bearing issues only) and the existing tick already performs GitHub reads (harvester); the `reconcile` verb without `--autonomous` gives an offline-tick escape hatch untouched.
- Backward compatibility of the ledger namespace: #279's existing key files carry no `kind` field — the U3 baseline reader must treat kind-absent files as write records (asserted in U3 scenario 11's fixtures using real #279-shaped files).

---

## Sources

- Issue #295 (requirements, corrected herein) and its brainstorm `docs/brainstorms/2026-06-28-board-saga-reconciliation-requirements.md`; readiness review `docs/reviews/` (per issue Sources).
- Shipped #279 writer: `plugins/saga/scripts/outcome_board_sync.py` (ledger `:89-113`, skip-on-key `:318`, retry/record `:343-418`); certificate `plugins/saga/scripts/reversibility_certificate.py:239,281`; wiring `plugins/saga/scripts/outcome.py:448,640-656`; plan `docs/plans/2026-06-29-reversibility-certificate-plan.md`.
- Harvester completion semantics: `plugins/saga/scripts/outcome_orchestrator.py:117-124,145-200`; `plugins/saga/scripts/outcome_github.py:79-92`.
- Schema status resolution decision: `docs/engineering-journal/DECISIONS.md` `{#outcome-board-status-schema-resolve-326}`.
- Operator decisions this session (2026-07-03): contract-aware + stateReason closes; `/outcome`-boundary trigger; writer-emitted field class.
- Doc-review probes (2026-07-03, live gh against this repo): `gh issue view --json state,stateReason` → `COMPLETED` raw values; `--json projectItems` → per-project `{status:{name},title}` (basis for revised KTD7/U1); `closedByActorLogin`/`closedBy` rejected as unknown fields; `gh api .../issues/279/events` closed event carries `actor.login`.
