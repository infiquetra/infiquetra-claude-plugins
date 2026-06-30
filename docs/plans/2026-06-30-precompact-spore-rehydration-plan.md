---
title: "PreCompact Spore — Re-ground the Continuing Session on Structured Facts, Not Prose"
type: feat
status: active
date: 2026-06-30
origin: docs/brainstorms/2026-06-27-precompact-spore-rehydration-requirements.md
---

# PreCompact Spore — Re-ground the Continuing Session on Structured Facts, Not Prose

## Summary

Add a two-hook "spore" to the saga plugin so that when a long session auto-compacts mid-run, the
continuing session re-grounds on structured saga facts (the OutcomeOrchestrator ready frontier + the
single active saga box) instead of only the harness prose summary. A `PreCompact` hook freezes those
facts to a worktree-stable, session-keyed cache at the compaction boundary; a new `SessionStart`
hook matched on `source == compact` reads that cache and re-injects it as a self-describing
`additionalContext` block. The existing `/resume` path, tick chain, and `state.json` model are not
touched — the spore is an additive cache.

## Problem frame

`/resume` is already fully durable, but it is an *explicit, fresh-session* cold restart. The gap is the
**implicit, mid-run auto-compaction boundary**: the same session keeps running on the harness prose
summary and never re-runs `/resume`. For a long `/outcome` campaign that eats multiple compactions, the
DAG frontier (open leaf ids, ready set, per-leaf state) is computed **derived-on-read and never
persisted** (`outcome_projection.py`, `outcome.py:333` `derive_states`, `outcome.py:362` `status`). If
that derivation isn't in the compacted context, the continuing agent cannot reconstruct where it is.
Nothing today writes saga facts at the compaction boundary (`hooks.json` registers no `PreCompact`, and
the lone `SessionStart` hook is matched `startup|resume` — `compact` is unmatched).

This plan consumes the brainstorm `docs/brainstorms/2026-06-27-precompact-spore-rehydration-requirements.md`
(maturity `requirements-ready`) and its readiness review
`docs/reviews/2026-06-27-precompact-spore-rehydration-readiness.md` (verdict READY, 0 P0/P1 open). It
carries the brainstorm's R1–R13 forward as this plan's requirements (same numbering for 1:1
traceability) and resolves the five `/plan`-deferred questions in the KTDs below.

---

## Grounding corrections (verified this session against docs + source)

Two facts found during HOW-grounding materially change the design rationale the brainstorm assumed.
They do not change the operator scope (Q1=A frontier + single saga; Q2=A persist + re-inject), only
how a requirement is satisfied — recorded here so the reviewer and implementer don't re-derive them.

| # | Brainstorm assumed | Verified reality | Consequence |
|---|---|---|---|
| GC1 | The 10k `additionalContext` cap is a **hard truncation** that could **drop the ready frontier → campaign deadlock** (R5; agy+codex P1). | The harness **spills to a file**: if the value exceeds 10,000 chars it writes the full text to the session dir and hands Claude a path + short preview (Claude Code hooks reference). | The frontier is **never lost by the harness**. The ≤budget policy survives but its *purpose* shifts: keep the resumable core **inline in the preview** for instant re-grounding rather than behind a file read. See KTD2. |
| GC2 | Re-injection "extends the existing pattern" in `stale_main_session_hook.py` (needs the compact branch + full-payload parse wired in). | Multiple `SessionStart` hooks **all** inject ("Claude receives all of the values"); the existing hook is matched `startup\|resume`. | Add a **separate** `compact`-matched hook; leave the stale-main hook untouched. No coupling, no regression risk to startup/resume. See KTD1. |

A precision fix also lands: the PreCompact auto-vs-manual distinction is the **`trigger`** field
(`auto`/`manual`), not `source` (the brainstorm's "matchers `auto`+`manual`" is correct for the
matcher; the stdin field name is `trigger`).

---

## Requirements

Carried forward from the brainstorm (origin R-IDs preserved). The reviewer verifies the shipped work
against these.

**Spore content — the structured spine (Q1=A):**

- **R1** — The spore is structured keyed fields, not prose and not a re-dump of the tick log.
- **R2** — It carries the single active saga box: `saga_id`, `lifecycle_phase`, `phase_status`,
  `status`, `next_step` — the five fields present in `state.json`'s `_saga_summary` (`saga.py:749-769`).
  `blockers` and `open_questions` are **not** in the index summary; read them from the latest tick
  envelope (`_tick_snapshot`, `saga.py:780-787`) when present. `checks_run` is **dropped from the box** —
  it is persisted in neither the index nor the tick snapshot (verified), so it cannot be carried. *(C1)*
- **R3** — It carries the OutcomeOrchestrator DAG, computed-and-frozen at PreCompact: open leaf ids,
  the ready frontier, and per-leaf state grounded in real derived fields — `{leaf_id, state, gated,
  last_completion_event_ref}` from `outcome.status()`/`derive_states()`, never an invented "verdict."
- **R4** — It carries pointers to canonical artifacts (outcome-spec path, issue refs, plan/work doc
  paths, source tick path), not their contents.
- **R5** — The serialized spore fits a deterministic byte budget via fixed ordering: the resumable core
  (`{leaf ids, state, ready frontier, saga box}`) first and **never dropped**; then bounded per-leaf
  refs; drop completed/`done` leaves, then evidence/waiting-leaf detail, before ever truncating the
  frontier; any drop is logged as a counted pointer ("+K more — see `<spec>`"), never silent.
  **Degenerate case (F3):** if the resumable core ALONE exceeds the budget, emit it in full anyway and
  accept the harness spill-to-file (GC1 — the full text incl. the frontier is preserved behind a file
  pointer, never dropped), logging that even the core spilled (counted, not silent).

**The two-hook mechanism (Q2=A):**

- **R6** — A `PreCompact` hook (matchers `auto` **and** `manual`) writes the spore to
  `<git-common-dir>/saga-spores/<session_id>.json` — worktree-stable, session-isolated.
- **R7** — A `SessionStart` path on `source == "compact"` (matcher wired in `hooks.json`; parses
  `source`/`session_id`/`cwd`) reads the matching spore and emits it as `additionalContext`.
- **R8** — Ordering: read → **build the full `additionalContext` string** → unlink → emit, so the spore
  is consumed before emit (consume-and-reset) and only the rare emit step can fail after the unlink. This
  is **at-most-once** delivery: a crash after unlink loses that one re-grounding window (the session
  falls back to the harness prose — no regression, and the next compaction re-freezes), which is the
  deliberate trade vs. re-injecting a stale spore. *(F7)*
- **R9** — Injection is session-keyed by `<session_id>` (no cross-session leakage). The active-saga
  *content* is resolved via `state.json:active_saga_id` (`saga.py:821`); the spore carries `saga_id` +
  repo root so SessionStart can detect and skip a mismatch. **Known limitation:** concurrent sessions
  in the *same* working directory fall back to per-repo last-writer-wins.

**Correctness & authority:**

- **R10** — The injected block is self-describing (provenance: `generated_at`, `saga_id`, spec revision,
  tick path, canonical refs) and leads with an explicit conflict instruction: structured facts are
  authoritative for **durable** state on conflict, but newer in-flight progress in the summary is real —
  reconcile, do not regress.
- **R11** — Nothing on the existing `/resume` path or the tick/`state.json` model changes; the spore is
  an additive cache, the anchor never the authority.

**Robustness:**

- **R12** — Both hooks degrade silently **and** on a deadline: any failure → compaction proceeds /
  session continues (exit 0, no block, no raise); the PreCompact freeze runs under a hard wall-clock
  timeout and skips the spore if exceeded, so it never stalls the compaction.
- **R13** — The PreCompact write and the SessionStart read agree on path/format, covered by a seam
  round-trip test: write a spore from a synthetic saga+outcome (incl. an over-budget campaign), assert
  SessionStart emits the expected self-describing `additionalContext` within budget, and assert a
  mismatched-session spore is **not** injected.

---

## Key Technical Decisions

- **KTD1 — A separate `compact`-matched `SessionStart` hook, not a fold into the stale-main hook.**
  Verified that multiple SessionStart hooks all inject (GC2) and the existing hook is matched
  `startup|resume`. A new `compact_spore_session_hook.py` matched `compact` keeps concerns separate, so
  the stale-main startup/resume behavior carries zero regression risk and each hook stays single-purpose.
  Rejected alternative: broadening the stale-main matcher and branching inside it — couples two unrelated
  features and risks the proven startup/resume path.

- **KTD2 — Budget the spore to ~9,000 chars to stay *inline*; the 10k cap is spill-to-file, not
  truncation (GC1).** The harness preserves the full text behind a file path when over 10k, so the goal
  is not "avoid harness data loss" but "keep the resumable core in the immediately-visible preview" so
  the continuing agent re-grounds without a file read. The serializer self-limits with the deterministic
  R5 ordering and emits a counted pointer to the canonical spec for dropped detail. If even the
  resumable core exceeds budget, it is emitted in full (accepting the harness spill) and the core-spill is
  logged — correctness over inlining (the R5 degenerate case).

- **KTD3 — Freeze the DAG box by calling `outcome.status()`, not by re-deriving from primitives.**
  `outcome.status(repo_root, outcome_id)` (`outcome.py:362-389`) already returns
  `{outcome_id, spec_revision, states, counts, frontier, complete}` derived-on-read, with the U8
  cross-surface fix (negative-terminal leaves never re-listed as dispatchable) baked in. The spore is a
  trimmed serialization of that single source of truth (honors R17 — never read state from a stored
  scalar). The per-leaf `gated` flag comes from the spec node; `last_completion_event_ref` from the
  latest completion event. Rejected: hand-assembling `ready_frontier()` + `derive_states()` + ledger
  reads in the hook — duplicates `status()` and risks the two surfaces drifting.

- **KTD4 — `outcome_id` discovery is leaf-id-authoritative with a bounded best-effort store-scan
  fallback, NOT a new saga field.** The `Saga` dataclass carries no `outcome_id` (`saga.py:138-226`), but
  the leaf saga id encodes it (`leaf-<outcome_id>-<subplot_id>`, `outcome_dispatcher.py:125`) and outcome
  stores live at `<git-common-dir>/saga-outcomes/<outcome_id>/` (`outcome_store.py:58,149`). Resolution
  (deadline-bounded, in order):
  (1) **leaf-id fast-path is authoritative** — if the active saga id matches `leaf-<outcome_id>-<subplot_id>`,
  parse `outcome_id` (O(1), unambiguous; covers the dominant campaign case where the session attends a leaf).
  (2) else **best-effort scan** of `saga-outcomes/` by store mtime (newest `ledger.jsonl` mtime, falling
  back to the store-root dir mtime), short-circuiting on the first **non-complete** store
  (`status()["complete"] == False`) so the worst-case `N`×`status()` cost is bounded and runs under the
  freeze deadline (KTD7).
  (3) if **two or more** non-complete stores exist and no leaf-id resolved → **omit the DAG box and log
  the ambiguity** (single-saga-only spore); never inject a guessed DAG. *(F2 / agy: a paused campaign + a
  hotfix would otherwise inject the wrong frontier — "don't guess on ambiguity.")*
  (4) if none resolves → single-saga-only.
  Resolves the brainstorm's open KD4 with no schema change and stays derived-on-read. Rejected: adding
  `Saga.outcome_id` (agy's preference) — a schema change requiring every `/outcome` command to populate
  it, for a fact the leaf-id already carries; the ambiguity it targets is closed by step (3) instead.

- **KTD5 — Spore keyed by `session_id` (filename), content by `active_saga_id`; no session→saga map in
  v1.** `session_id` arrives on both hooks' stdin (verified) so the filename agrees end-to-end; *which*
  saga's facts go in is `state.json:active_saga_id` (per-worktree last-write). These are orthogonal and
  both work without a map. The full `session_id→saga_id` map is **deferred**: `session_id` does not reach
  `saga.py save` today (no `--session-id` arg, no `CLAUDE_SESSION_ID` usage), so there is no clean
  save-time binding source. Same-cwd concurrent sessions remain the acknowledged R9 limitation rather
  than a silent failure (the spore self-identifies its `saga_id`+repo-root for mismatch-skip).

- **KTD6 — Crash-safe ordering, atomic writes, and orphan hygiene mirror `outcome_store`.** PreCompact
  writes the spore temp-then-`os.replace` (no torn read); SessionStart reads → builds the full block →
  unlinks → emits (R8, at-most-once). On write, PreCompact also best-effort unlinks `saga-spores/*.json`
  older than `SPORE_TTL_DAYS` (default `7`) to bound orphan accumulation from sessions that compact but
  never resume into a `SessionStart(compact)` (errors ignored; under the deadline) *(F4)*. Reuse the
  git-common-dir resolution helper `outcome_store.resolve_common_dir()` (`outcome_store.py:93-126`) and
  the `_safe_name` path-traversal guard (`outcome_store.py:84-90`) rather than re-implementing them.

- **KTD7 — Degrade silently AND on a deadline (R12).** Any failure in either hook → exit 0, no
  `decision: block`, no traceback. The PreCompact freeze+serialize runs under a hard wall-clock timeout
  (`SPORE_DEADLINE_S`, default `1.5`); if exceeded the hook writes nothing rather than stalling the
  compaction the user is waiting on. **Mechanism (F1):** the freeze includes blocking subprocess work
  (`outcome.status()` → `resolve_common_dir` shells out to `git rev-parse`; the KTD4 scan loops
  `status()`) that a between-steps clock check cannot interrupt mid-call, so the deadline is a true
  wall-clock interrupt — `signal.signal(SIGALRM, handler)` + `signal.setitimer(ITIMER_REAL,
  SPORE_DEADLINE_S)` wrapping the ENTIRE freeze (valid because a PreCompact hook runs on the main thread
  of a standalone Unix process; macOS/Linux is the target). On `SIGALRM` the handler raises, the hook
  catches it, writes nothing, and exits 0. (A child-process `subprocess(..., timeout=)` or a
  `thread.join(deadline)` are acceptable equivalents.) A between-steps check is kept only as
  belt-and-suspenders, never the primary bound.

- **KTD8 — No saga tick written at PreCompact (resolves deferred Q4 = no).** Writing a tick at the
  boundary would re-introduce the very worktree-path hazard KD3/KTD6 fixes (ticks land under the
  worktree-relative `.claude/saga`, `saga.py:44`) and risks a hook corrupting the durable tick chain.
  The spore is a separate git-common-dir cache; durable state stays owned by the explicit save path.
  Deferred as a non-goal.

---

## High-Level Technical Design

The mechanism is one write-only producer and one read-and-inject consumer sharing a session-keyed file
in the worktree-stable cache. The serializer/loader core (U1) is pure and unit-tested offline; the two
hooks (U2/U3) are thin shells over it.

```
long /outcome session fills the window
        │
        ▼
[PreCompact hook · matcher auto|manual]            (U2 — write-only, ≤1.5s, exit 0 on any failure)
  stdin: {session_id, cwd, trigger}
  ├─ resolve repo_root from cwd
  ├─ active_saga_id ← <repo>/.claude/saga/state.json        (KTD5)
  ├─ outcome_id ← leaf-id parse OR newest non-complete saga-outcomes store   (KTD4)
  ├─ freeze ← outcome.status(repo_root, outcome_id)         (KTD3, derived-on-read)
  ├─ serialize ≤ budget, frontier never dropped             (R5/KTD2)
  └─ atomic write → <git-common-dir>/saga-spores/<session_id>.json   (R6/KTD6)
        │
        ▼
   harness compacts → continuing session, source=compact
        │
        ▼
[SessionStart hook · matcher compact]              (U3 — separate hook, KTD1)
  stdin: {session_id, cwd, source}
  ├─ read <git-common-dir>/saga-spores/<session_id>.json
  ├─ skip if saga_id/repo-root mismatch                     (R9)
  ├─ unlink BEFORE emit                                     (R8/KTD6)
  └─ emit self-describing additionalContext                 (R7/R10)
        │
        ▼
continuing session re-grounds on structured facts, reconciles newer in-flight work (R10)
```

---

## Implementation Units

Dependency order: **U1 → (U2, U3) → U4 → U5 → U6**. U1 is the pure core; U2/U3 are independent thin
hooks over it; U4 wires both ends (dead-wiring guard); U5 proves the seam end-to-end; U6 ships.

### U1. Spore serializer/loader core (`saga_spore.py`)

**Goal:** A pure, offline-testable module that resolves the active saga + outcome, freezes the DAG box,
and serializes/deserializes the budgeted, self-describing spore — the heart of the feature, with the
two hooks as thin callers.

**Requirements:** R1, R2, R3, R4, R5, R9, R10 (content + budget + provenance + mismatch fields).

**Dependencies:** none (reuses existing `outcome.py`, `outcome_store.py`, `saga.py` as imports).

**Files:**
- create `plugins/saga/scripts/saga_spore.py`
- create `tests/test_saga_spore.py`

**Approach:** Follow the house pattern of `outcome_store.py` — pure-ish functions over explicit values,
dependency-injected `runner`/`now`, **no I/O at import**, `sys.path` shim to import sibling
`outcome`/`outcome_store`/`saga` modules. Key functions:

`spore_path(common_dir, session_id) -> Path` — `<common-dir>/saga-spores/<_safe_name(session_id)>.json`,
reusing `outcome_store._safe_name` and `resolve_common_dir`.

`resolve_active_saga(repo_root) -> dict | None` — read `<repo_root>/.claude/saga/state.json`; take the
`sagas{active_saga_id}` summary for the 5 index-resident R2 fields (`saga_id`, `lifecycle_phase`,
`phase_status`, `status`, `next_step`) and read the latest tick envelope for `blockers`/`open_questions`
when present (C1 — `_saga_summary` omits them; `checks_run` is dropped). None if absent/malformed.

`resolve_outcome_id(active_saga_id, common_dir, *, now) -> str | None` — KTD4 order: leaf-id parse
fast-path (authoritative), else bounded best-effort scan of `saga-outcomes/` by ledger mtime,
short-circuiting on the first non-complete store; returns None (→ DAG omitted) when ≥2 non-complete
stores are ambiguous or none resolves (F2 — never guess the DAG).

`freeze_dag(repo_root, outcome_id) -> dict | None` — call `outcome.status()` (which internally gathers
the terminal set correctly; do **not** call `completed_subplots` directly — its default
`successful_only=True` omits failed/rejected/stalled, C2); attach per-leaf `gated` (spec node) +
`last_completion_event_ref`; None if no outcome.

`build_spore(repo_root, session_id, *, now) -> dict` — assemble `{provenance, saga_box, dag, pointers}`;
DAG is None for the single-saga case.

`serialize(spore) -> str` — render the self-describing block (leading conflict instruction + provenance,
R10) then the facts, applying the R5 priority ordering and `SPORE_BUDGET_CHARS` (default `9000`);
emit the counted-drop pointer when over budget; return the final string.

`load_and_validate(text, expected_session_id, expected_repo_root) -> str | None` — parse, mismatch-skip
on `saga_id`/repo-root (R9), return the renderable block or None.

**Patterns to follow:** `plugins/saga/scripts/outcome_store.py` (git-common-dir resolution `:93-126`,
`_safe_name` `:84-90`, atomic write-once discipline, injected `runner`/`now`, no import I/O);
`outcome.py:362` `status()` for the frozen DAG shape; `saga.py` `state.json` shape (`update_index`
`:792-837`) for the saga box fields.

**Test scenarios:**
- *Happy path (single saga):* given a `state.json` with one `active_saga_id` and no outcome, `build_spore`
  returns a saga box with the R2 fields and `dag: None`; `serialize` produces a block ≤ budget that
  leads with the conflict instruction and includes `saga_id`/provenance.
- *Happy path (campaign):* given a synthetic outcome spec + completion events on disk, `freeze_dag`
  returns `frontier`, per-leaf `state`/`gated`, and `counts` matching a direct `outcome.status()` call;
  the ready frontier appears in the serialized core.
- *Budget edge (over-budget campaign):* given an outcome wide enough to exceed `SPORE_BUDGET_CHARS`,
  `serialize` keeps the saga box + ids + states + **full ready frontier** inline, drops completed then
  waiting-leaf detail with a counted "+K more — see `<spec>`" pointer, and the result is ≤ budget; assert
  the drop is logged (no silent cap).
- *Core-over-budget (F3):* given a ready frontier wide enough that the resumable core ALONE exceeds the
  budget, `serialize` emits the full frontier anyway (never dropped) and logs that the core spilled
  (counted) — accepting the harness spill-to-file rather than truncating the frontier.
- *Outcome discovery (KTD4/F2):* `resolve_outcome_id` parses `leaf-ship-auth-U3` → `ship-auth`; with no
  leaf id, picks the newest non-complete store and skips a `complete` one; returns None when
  `saga-outcomes/` is empty; with **two** non-complete stores and no leaf id, returns None (DAG omitted,
  ambiguity logged — never a guessed outcome).
- *Mismatch (R9):* `load_and_validate` returns None when the spore's `saga_id` or repo-root differs from
  the caller's expected values; returns the block when they match.
- *Error paths:* missing/malformed `state.json` → `resolve_active_saga` returns None (no raise);
  git-unavailable `resolve_common_dir` raises `OutcomeStoreError` and the caller treats it as
  "no spore" (covered in U2/U3); `freeze_dag` on a corrupt spec returns None, not a traceback.

**Verification:** `tests/test_saga_spore.py` passes; the module imports with no filesystem/subprocess
side effects (assert via an import-under-fake-cwd test mirroring `outcome_store`'s contract); a
hand-built campaign fixture round-trips through `serialize` → `load_and_validate` unchanged.

### U2. PreCompact hook (`precompact_spore_hook.py`)

**Goal:** A write-only hook that, at the compaction boundary, freezes the spore via U1 under a wall-clock
deadline and writes it atomically to the git-common-dir — never blocking or stalling compaction.

**Requirements:** R6, R12 (and exercises R1–R5/R9/R10 via U1).

**Dependencies:** U1.

**Files:**
- create `plugins/saga/hooks/precompact_spore_hook.py`
- create `tests/test_precompact_spore_hook.py`

**Approach:** Read stdin JSON (`session_id`, `cwd`, `trigger`) tolerantly (mirror
`stale_main_session_hook._read_cwd_from_stdin` — return None/exit 0 on empty/malformed). Resolve repo
root from `cwd` (`git rev-parse --show-toplevel`). Run `saga_spore.build_spore` + `serialize` under a hard
`SIGALRM`/`setitimer` wall-clock deadline (`SPORE_DEADLINE_S`, KTD7) wrapping the **entire** freeze — not
a between-steps clock check, since a blocking `status()`/`git` call cannot be interrupted between steps
(F1). On timeout, write nothing. Resolve the common dir, ensure `saga-spores/` exists, write
`<session_id>.json` temp-then-`os.replace`, then best-effort sweep spores older than `SPORE_TTL_DAYS`
(F4/KTD6). **Always exit 0**; never print a `decision`. Guard defensively on `trigger ∈ {auto, manual}`
even though the matcher filters, so a broadened matcher can't misfire.

**Patterns to follow:** `plugins/saga/hooks/stale_main_session_hook.py` (stdin parse, `_run` git helper,
quiet-on-error, always exit 0); `outcome_store.py` atomic write + common-dir resolution.

**Test scenarios:**
- *Happy path:* drive the hook as a real subprocess with a `{session_id, cwd, trigger: auto}` payload in a
  `tmp_path` git repo seeded with a `state.json` + outcome store; assert a `saga-spores/<session_id>.json`
  appears under the repo's git-common-dir and parses to the expected spore.
- *Manual trigger:* same with `trigger: manual` → spore written (R6 covers both).
- *No active saga:* empty/absent `state.json` → no spore written, exit 0, no stdout.
- *Deadline (R12/F1):* monkeypatch a `sleep` **inside** `outcome.status()` to exceed `SPORE_DEADLINE_S` →
  assert the hook aborts at the deadline (wall-clock ≤ `SPORE_DEADLINE_S` + margin), writes nothing, and
  exits 0 — proving the interrupt bounds an in-progress blocking call, not just between steps.
- *Orphan sweep (F4):* with a stale `saga-spores/old.json` (mtime > `SPORE_TTL_DAYS`) present, a
  PreCompact write removes it while leaving a fresh spore untouched.
- *Error paths:* malformed stdin → exit 0 silent; git-unavailable (cwd not a repo) → exit 0, no spore;
  unwritable common dir → exit 0, no raise.
- *Never blocks:* assert the hook never prints `{"decision": "block"}` and never exits non-zero.

**Verification:** `tests/test_precompact_spore_hook.py` passes; nothing lands under the repo-root
`.claude/` (the spore is under the git-common-dir); a deliberately slow freeze is provably skipped.

### U3. SessionStart(compact) re-inject hook (`compact_spore_session_hook.py`)

**Goal:** A separate `compact`-matched SessionStart hook that reads the matching spore, unlinks it before
emitting, and injects it as a self-describing `additionalContext` block.

**Requirements:** R7, R8, R9, R10.

**Dependencies:** U1.

**Files:**
- create `plugins/saga/hooks/compact_spore_session_hook.py`
- create `tests/test_compact_spore_session_hook.py`

**Approach:** Read stdin JSON (`source`, `session_id`, `cwd`). If `source != "compact"` → exit 0 silent
(defensive even though the matcher filters). Resolve repo root + common dir, read
`saga-spores/<session_id>.json`. Run `saga_spore.load_and_validate` (mismatch-skip, R9). **Unlink the
spore before** emitting (R8/KTD6) so a crash can't double-inject. Emit the official SessionStart shape
`{"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": <block>}}` (reuse the
exact shape from `stale_main_session_hook.py:235-244`). No spore or any failure → exit 0, no output.

**Patterns to follow:** `plugins/saga/hooks/stale_main_session_hook.py:227-245` (output shape, always
exit 0); U1 `load_and_validate`.

**Test scenarios:**
- *Happy path:* with a spore present for `<session_id>`, the hook emits valid SessionStart JSON whose
  `additionalContext` contains the conflict instruction + ready frontier + saga box, and the spore file
  is **gone** afterward (unlink-before-emit).
- *Unlink-before-emit ordering (R8):* simulate a failure after unlink but before print (monkeypatch
  `print` to raise) → the spore is already removed (assert no re-inject on a second run).
- *Mismatch (R9):* a spore whose `saga_id`/repo-root doesn't match → no injection, exit 0; assert the
  mismatched spore is **not** consumed (left for its owner) — only matching spores are unlinked.
- *No spore:* missing file → exit 0, no stdout.
- *Wrong source:* `source: startup` payload → exit 0 silent (does not read or unlink).
- *Error paths:* malformed stdin / git-unavailable / unreadable spore → exit 0, no raise.

**Verification:** `tests/test_compact_spore_session_hook.py` passes; a consumed spore never re-injects on
a subsequent compaction; a foreign-session spore is left intact.

### U4. Hook registration in `hooks.json`

**Goal:** Wire both ends so the producer and consumer are live — the dead-wiring guard (a spore writer
with no reader, or vice-versa, is the failure the brainstorm KD2 calls out).

**Requirements:** R6, R7 (registration).

**Dependencies:** U2, U3.

**Files:**
- modify `plugins/saga/hooks/hooks.json`
- modify `tests/test_saga_plugin.py` (or add a focused registration assertion)

**Approach:** Add a `PreCompact` block with matcher `"auto|manual"` → `precompact_spore_hook.py`, and a
second `SessionStart` entry with matcher `"compact"` → `compact_spore_session_hook.py` (a sibling array
entry alongside the existing `startup|resume` one — both fire and both inject, GC2/KTD1). Use the
`${CLAUDE_PLUGIN_ROOT}/hooks/...` command form already used by every entry. Validate the JSON parses
(`python3 -m json.tool`).

**Patterns to follow:** the existing entries in `plugins/saga/hooks/hooks.json` (command form, matcher
alternation as in `startup|resume`).

**Test scenarios:**
- *Registration assertion:* a test loads `hooks.json` and asserts (a) a `PreCompact` matcher covering
  `auto` and `manual` points at `precompact_spore_hook.py`; (b) a `SessionStart` entry matched `compact`
  points at `compact_spore_session_hook.py`; (c) the original `startup|resume` stale-main entry is
  unchanged (no regression).
- *JSON validity:* `hooks.json` parses as valid JSON.

**Verification:** `hooks.json` parses; the registration test passes; the existing stale-main entry is
byte-unchanged.

### U5. End-to-end seam round-trip test

**Goal:** Prove the PreCompact write and the SessionStart read agree on path/format across the real
process boundary — the components-present ≠ end-to-end guard (R13).

**Requirements:** R13 (and integration coverage of R5/R9/R10).

**Dependencies:** U1, U2, U3, U4.

**Files:**
- create `tests/test_spore_seam_roundtrip.py`

**Approach:** Build a real throwaway git repo under `tmp_path` (mirror
`tests/test_stale_main_session_hook.py:41-85` — real `git init`, deterministic identity, no global
config leak), seed a `state.json` + a synthetic outcome spec + completion events (including an
over-budget campaign), then drive **both hooks as real subprocesses** with realistic stdin payloads.
Assert the full pipeline: PreCompact writes → SessionStart reads/unlinks/injects.

**Patterns to follow:** `tests/test_stale_main_session_hook.py` (real-git + real-subprocess harness,
`additionalContext` assertions, nothing under repo-root `.claude/`); existing outcome fixtures in
`tests/test_outcome_*.py` for building a spec + completion events.

**Test scenarios:**
- *Seam happy path:* PreCompact(auto) → SessionStart(compact) yields an `additionalContext` block that
  contains the ready frontier, open leaves with per-leaf state, and the self-describing provenance
  header; the spore file is gone after SessionStart.
- *Over-budget (AE2/R5):* a wide campaign stays ≤ budget, keeps the full frontier inline, and carries a
  counted-drop pointer for waiting-leaf detail.
- *Mismatched session (AE4/R9):* a SessionStart with a different `session_id` injects nothing and does
  not consume the first session's spore.
- *Degrade (AE3/R12):* a PreCompact that finds no resolvable saga writes nothing → SessionStart injects
  nothing; both exit 0 (session continues on the prose summary, no regression).
- *Worktree stability (AE6/KD3):* write the spore from a linked worktree's cwd, remove the worktree, and
  assert SessionStart still reads it from the shared git-common-dir.

**Verification:** `tests/test_spore_seam_roundtrip.py` passes; the over-budget case demonstrably retains
the frontier; the degrade case demonstrably injects nothing without error.

### U6. Release surfaces + journal

**Goal:** Make the installed-plugin metadata tell the same story as the diff and capture the durable
decisions (per the repo's release-surface rule and the auto-journal directive).

**Requirements:** none (release/docs; non-feature-bearing).

**Dependencies:** U1, U2, U3, U4, U5.

**Files:**
- modify `plugins/saga/.claude-plugin/plugin.json` (version bump)
- modify `.claude-plugin/marketplace.json` (matching version)
- modify `plugins/saga/CHANGELOG.md` (feature entry)
- modify `plugins/saga/skills/*/references/saga-spec.md` (document the spore cache as an additive,
  non-canonical artifact, if a §exists for cache/storage) — confirm during U6 whether a doc note is
  warranted
- modify `docs/engineering-journal/DECISIONS.md` and `docs/engineering-journal/LEARNINGS.md`

**Approach:** Bump the saga plugin version (current `plugins/saga/CHANGELOG.md` head is ≥ 0.42.0 — pick
the next minor; confirm the exact current version at execution time) and mirror it in
`marketplace.json`. Add a CHANGELOG entry describing the two-hook spore. Record KTD1–KTD8 in
`DECISIONS.md` (the journal is the canonical KTD record) and a LEARNINGS entry for the two grounding
corrections (GC1 spill-to-file, GC2 multi-SessionStart injection) with `file:line` evidence.

**Patterns to follow:** prior version-bump commits in `plugins/saga/CHANGELOG.md`; the marketplace
edit-guard in auto-memory (`old_string` must include the prior entry's `}` + the `]` + the `"version"`
line; `python3 -m json.tool` after).

**Test scenarios:** `Test expectation: none -- release metadata + docs; covered by the existing version
drift-guard test and `python3 -m json.tool` validation.`

**Verification:** `marketplace.json` and `plugin.json` agree on the new version; the drift-guard test
passes; `CHANGELOG.md` has a dated entry; DECISIONS/LEARNINGS entries land in the same PR.

---

## Risks & Dependencies

| Risk | Likelihood | Mitigation |
|---|---|---|
| Hook stalls the compaction the user is waiting on | Low | Hard wall-clock deadline (KTD7/R12); freeze is bounded `status()` + serialize; skip-on-timeout, exit 0. |
| Spore over-budget hides the frontier behind a file pointer | Low | KTD2 budgets to ~9k (under 10k) and R5 keeps the frontier inline + never dropped; U5 over-budget test proves it. |
| Same-cwd concurrent sessions get the wrong saga's facts | Low (solo operator) | Acknowledged R9 limitation; spore self-identifies `saga_id`+repo-root for mismatch-skip; full session→saga map deferred (KTD5). |
| Claude Code hook payload field names change upstream | Low | Defensive stdin parsing (tolerate missing fields, exit 0); field names verified against the current hooks reference this session. |
| `outcome.status()` raises on a corrupt/partial store mid-campaign | Low | `freeze_dag` returns None on error; the spore degrades to single-saga-only; never a traceback (R12). |

**Dependency:** none external. The feature imports existing in-repo modules (`outcome`, `outcome_store`,
`saga`) and the verified Claude Code hook contract (`PreCompact` trigger fields; `SessionStart`
`source=compact` + `additionalContext` ≤10k spill-to-file).

---

## Scope Boundaries

**In scope:** the two-hook spore (PreCompact write + SessionStart(compact) re-inject); DAG frontier +
single-saga content frozen via `outcome.status()`; git-common-dir session-keyed storage; deterministic
≤budget serialization with the frontier never dropped; the self-describing authority block; silent +
bounded-time degrade; the seam round-trip test; release surfaces + journal.

**Out of scope (true non-goals):**
- The existing `/resume` path, the tick chain, and the `state.json` model — unchanged (R11).
- Replacing the harness prose summary — impossible (it's already injected); the spore augments only.
- Persisting the frontier into the canonical `outcome-spec.json` — the spore is a boundary cache, not a
  schema change; the frontier stays derived-on-read everywhere else.
- A general event-sourcing rewrite — the append-only-log + rebuildable-index substrate already exists.

**Deferred to Follow-Up Work (planned, later PR/issue):**
- The full `session_id → saga_id` map for true same-cwd multi-session disambiguation (KTD5) — blocked on
  a clean save-time binding source (`session_id` reaching `saga.py save`).
- Writing a final saga tick at PreCompact (Q4/KTD8) — blocked on a git-common-dir-safe tick path so it
  doesn't re-introduce the worktree-path hazard.

---

## Execution (operator-pinned)

**Backend: `inline`.** Claude is the orchestrator, verifier-of-record, and **sole committer/pusher**.
Destination is **merge** (squash to main after `/doc-review` → `/work` → green CI).

**agy is a delegated worker** via the infiquetra `agy` plugin **v0.1.0** — invoked through
`/agy:delegate` or the packaged `agy-coder` bridge agent, **never** a hand-rolled `agy` shell call (the
contract forbids raw `agy`; the only supported path is `python3 plugins/agy/scripts/agy_delegate.py`).
Proposed unit assignment (final split confirmed at `/work`): the bounded, well-specified units go to
agy — **U2** (PreCompact hook shell), **U3** (SessionStart hook shell), and the **U5** seam-test
scaffolding; Claude owns the judgment seams **U1** (freeze/budget/discovery logic), **U4** (hooks.json
wiring), and **U6** (release + journal), and reviews + imports every patch agy returns.

**Delegation mechanics (per agy unit).** Each delegation is a `coder` envelope in **`mode=patch-only`**
(the coder default): agy runs inside a **disposable clone** (remotes stripped) and returns a
`diff.patch` in an evidence bundle under `.claude/agy/runs/<run-id>/`; Claude reviews that patch and is
the one who applies + commits it. Give each envelope an explicit **`write_set`** and the unit's
**verification command** — the wrapper requires orchestrator-supplied checks and the delegate may not
invent them:

- **U2** → write-set `plugins/saga/hooks/precompact_spore_hook.py`,
  `tests/test_precompact_spore_hook.py`; verification `uv run pytest tests/test_precompact_spore_hook.py`.
- **U3** → write-set `plugins/saga/hooks/compact_spore_session_hook.py`,
  `tests/test_compact_spore_session_hook.py`; verification
  `uv run pytest tests/test_compact_spore_session_hook.py`.
- **U5** → write-set `tests/test_spore_seam_roundtrip.py`; verification
  `uv run pytest tests/test_spore_seam_roundtrip.py`.

**Model: `Gemini 3.1 Pro (High)` (operator-pinned).** Pass this exact canonical string as the envelope
`model` field. The wrapper forwards `--model` **verbatim with no alias expansion** (`agy_delegate.py`
`_build_agy_argv`), and `agy 1.0.14 models` lists `Gemini 3.1 Pro (High)` as a valid value (verified
this session) — so the full TUI string is required; the short alias `pro` would hand agy an unlisted
string. **First-run check:** the live harness proof (`plugins/agy/docs/harness-proof.md`, 2026-06-30)
exercised the wrapper's default (`flash` → `Gemini 3.5 Flash (High)`), so the **first** agy delegation
at `/work` should confirm `Gemini 3.1 Pro (High)` executes cleanly end-to-end through the wrapper
(heavier model, longer runtime; the 900s `timeout_seconds` covers it) before relying on it for U2/U3/U5.

**Containment is wrapper-enforced, not a manual ritual.** The guarded wrapper already guarantees the
live repo changes only through Claude's review + apply: agy runs in a remote-stripped clone so it
**cannot push**; any commits it makes land in the throwaway clone and are flagged as `rogue_commits`
(→ `checks_failed`, blocking apply); changes outside the `write_set` are flagged
`out_of_scope_mutation`. Provenance is built in — the bridge agents are Bash-only (no Read/Edit/Write,
so a "Claude clone" solving locally is a contract breach), and `classify_transcript` /
`audit_harness_transcript.py` mark a run `real` only when the wrapper was invoked and no Claude
file-tool was used. The provenance signal is the run bundle (`agy_launched=true` + `git-proof.json`),
**not** a manual grep for `agy --model` (which lives only inside the wrapper). Claude's standing duties
remain: tightly specify each task (under-specification feeds wandering), run the **full test suite** as
the gate before importing a patch, and stay the sole committer/pusher. The two correctness seams
(U1 budget / never-drop-frontier; U3 unlink-before-emit ordering) get an in-session adversarial check
(advisory, not a gated team-execution verdict — the build is safe, no deploy/security surface).

---

## Sources / Research

- Upstream WHAT: `docs/brainstorms/2026-06-27-precompact-spore-rehydration-requirements.md`;
  readiness review `docs/reviews/2026-06-27-precompact-spore-rehydration-readiness.md` (READY).
- Frontier + per-leaf state (KTD3): `outcome.py:362-389` (`status`), `outcome.py:333-359`
  (`derive_states`), `outcome_spec.py:531-544` (`ready_frontier`), `outcome_store.py:350-373`
  (`completed_subplots`).
- Outcome discovery (KTD4): `outcome_dispatcher.py:125` (`leaf-<outcome_id>-<subplot_id>`),
  `outcome_store.py:58,149` (`saga-outcomes/<outcome-id>`).
- Storage / worktree stability (KTD6): `outcome_store.py:93-126` (`resolve_common_dir`),
  `outcome_store.py:84-90` (`_safe_name`); `saga.py:44` (`.claude/saga` worktree-relative).
- Active-saga resolution (KTD5/R9): `saga.py:792-837` (`update_index`, `active_saga_id` at `:821`);
  `saga.py:138-226` (`Saga` dataclass — no `outcome_id` field).
- Hook substrate (KTD1/R7): `plugins/saga/hooks/hooks.json` (no PreCompact; SessionStart matched
  `startup|resume`); `plugins/saga/hooks/stale_main_session_hook.py:227-245` (output shape, exit-0
  discipline); `tests/test_stale_main_session_hook.py:41-85` (real-git + real-subprocess test harness).
- Hook mechanics (GC1/GC2, verified this session via the Claude Code hooks reference): PreCompact stdin
  carries `session_id`/`cwd`/`trigger`(auto|manual)/`transcript_path`, is write-only (cannot inject,
  only `decision: block`); SessionStart(`source=compact`) injects `additionalContext`; >10k spills to a
  file + preview (not hard truncation); multiple SessionStart hooks all inject.
