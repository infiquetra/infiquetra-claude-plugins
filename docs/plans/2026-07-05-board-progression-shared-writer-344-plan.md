---
title: "board_progression.py — certificate-gated status writer shared by /outcome, /work, /loop"
type: feat
status: active
date: 2026-07-05
origin: https://github.com/infiquetra/infiquetra-claude-plugins/issues/344
---

# board_progression.py — certificate-gated status writer shared by /outcome, /work, /loop

Phase 0 item 6 (execution-order doc, row 6). Extract `/outcome`'s proven autonomous board-sync
writer into a plugin-agnostic module, wire two new consumers (`/work` post-merge, `/loop` render),
and add a derived idea→deploy arc renderer — all under the existing reversibility-certificate GATE
contract, widening *who writes* without widening *what may be written autonomously*.

## Problem & grounding

`/outcome`'s `outcome_board_sync.reconcile_board` (merged #279/#295) already proves the pattern:
every candidate board op is routed through `reversibility_certificate.authorize_write`
(`AUTHORIZED`/`GATE`, default-GATE), idempotency-keyed into a separate board-sync ledger, driven
with bounded retry, and recorded fail-loud (never silent skip). Today it has exactly one runtime
caller — `outcome.py:684` inside `advance`. `/work` still hands every post-merge Status/close move
to the operator by way of `mission-control` (`work/SKILL.md §4.3`, `:377`, "does not file or mutate
the issue itself"); `/loop` renders no idea→deploy progress at all.

Verified during planning:

- `reconcile_board` defined `outcome_board_sync.py:177`; sole runtime caller `outcome.py:684`
  (lazy `import outcome_board_sync` at `:652`); exercised directly by `tests/test_outcome_board_sync.py`.
- **`outcome_reconcile.py:256` is a second runtime consumer of `outcome_board_sync`'s helpers** (not of
  `reconcile_board`): it calls `sync._default_schema_path` (`:271`), `_resolve_status_map` (`:272`),
  `_parse_issue_ref` (`:285`), `_candidate_ops` (`:298`), and `_safe_ledger_name` (`:337`). Any of these
  that `board_progression` takes ownership of MUST be re-exported from `outcome_board_sync`, or
  `outcome_reconcile` breaks. Confirmed second consumer — the extraction is helper-surface-preserving.
- **The concrete production board_writer is `outcome.py:_default_board_writer` (`:452`)** — it maps each
  `OpKind` to an `sdlc_manager.py` (mission-control) subcommand and is *already* constructed from a CLI
  path at `outcome.py:1322`. Skill consumers (`/work`, `/loop`) are markdown that invoke CLIs, not Python
  importers, so `board_progression` must expose a CLI that resolves this concrete writer itself.
- `reversibility_certificate.authorize_write` is **already plugin-agnostic and closed-by-construction**:
  merge/deploy op-kinds are absent from `_REGISTRY` (default-GATE), `PARENT_ISSUE_CLOSE` is
  `ALWAYS_OPERATOR`→GATE (`reversibility_certificate.py:239-267`). The allowlist lives *there*, not in
  the writer.
- `status_card.py` has no `project_arc` today; `project_work` (`:246`) is the exact template — a
  gate-sequence `CardSpec` that is a pure function of durable saga fields, consulting no writable
  status column. `CardState` = {DONE ✓, IN_PROGRESS ◐, BLOCKED ⊘, FAILED ✗, HALTED ‖, NOT_REACHED ·}.
- `/loop`'s first principle (`loop/SKILL.md:41`) is "route and sequence; don't execute the phase work
  yourself"; `mission-control` owns boards (`:60`). `/loop` has **no existing hand-writes-the-board
  seam** — it defers by routing.
- Current `saga` version is **0.56.0** (the issue body's "0.51.0" is stale — this session shipped
  0.54.x→0.56.0). Bump target: **0.57.0**.

## Requirements

- **R1.** `plugins/saga/scripts/board_progression.py` exists: a plugin-agnostic primitive that, for a
  single candidate op, routes through `reversibility_certificate.authorize_write`, GATEs anything not
  AUTHORIZED (fail-loud record, never silent), idempotency-keys AUTHORIZED ops into an injected ledger
  dir, drives an injected `board_writer` with bounded retry, and returns a record dict — the exact
  contract lifted from `reconcile_board`'s per-op loop (`outcome_board_sync.py:293-441`).
- **R2.** `outcome_board_sync.reconcile_board` delegates each op's authorize/ledger/write/record to
  `board_progression`, keeping its `/outcome`-specific `derive_states` / `_candidate_ops` / drift-hold /
  schema-resolution logic. **Zero behavior diff**: `tests/test_outcome_board_sync.py` passes unchanged,
  no test-count regression.
- **R3.** Merge/deploy candidate ops return `GATE` from *every* consumer (`/outcome`, `/work`, `/loop`),
  structurally — `board_progression` re-derives no verdict; it is a pure consumer of the certificate.
- **R4.** An autonomous reversible write grows only the write-record ledger; it commits **zero new
  status fields** into any saga or issue artifact (HALT-not-degrade preserved).
- **R5.** `/work`'s post-merge phase fires allowlisted Status→Done and sub-issue-close through
  `board_progression` with **no operator prompt**; non-allowlisted ops (and merge/deploy) still prompt
  exactly as today.
- **R6.** `/loop`'s board involvement is bound principle-preservingly (see KTD3): `/loop` renders the
  arc and, in Drive mode, sequences to the destination command that owns the write; `/loop` does not
  itself autonomously mutate the board.
- **R7.** `status_card.py` gains `project_arc` — a pure function of durable saga fields (the same
  fields `project_work` reads) rendering an idea→deploy arc; no writable status field consulted.
- **R8.** `/loop` renders the arc via `project_arc` at Route / Drive / Resume entry, replacing any
  hand-narrated status.
- **R9.** Driving a saga through stages moves the mission-control card and closes the issue end-to-end
  without the operator hand-moving the card on any allowlisted transition (achieved via R5 + existing
  `/outcome`; `/loop` sequences it).

## Key Technical Decisions

**KTD1 — `board_progression` owns the *mechanism*; callers own the *policy*.** The new module extracts
only the per-op authorize→ledger→retry-write→record mechanism (issue KD1). Candidate-op derivation
stays caller-side: leaf-state in `outcome_board_sync`, post-merge-state in `/work`. The ledger dir is
an **injected parameter**, and `board_progression` carries its **own** atomic `_write_once` rather than
importing `outcome_store._write_once` (keeps it plugin-agnostic). `outcome_board_sync` keeps
`_board_sync_dir(store)` and passes it in. **Helper-surface preservation:** `outcome_reconcile:256`
calls `_default_schema_path`, `_resolve_status_map`, `_parse_issue_ref`, `_candidate_ops`, and
`_safe_ledger_name` on `outcome_board_sync`; `board_progression` may own `_safe_ledger_name` + the
per-op writer, but `outcome_board_sync` must **re-export** `_safe_ledger_name` (and keep the rest) so
`outcome_reconcile` is never stranded.

**KTD2 — merge/deploy gating is inherited, not re-implemented.** KD3 ("merge/deploy permanently gated
in every consumer") holds *structurally* because the allowlist lives in `reversibility_certificate`
and `board_progression` routes every op through `authorize_write`. A new consumer **cannot** widen the
autonomously-writable set without bypassing the certificate — which the single-writer design and R3
tests forbid. This is why the writer extraction does not itself expand autonomy surface.

**KTD3 — `/loop` is renderer + sequencer, not an autonomous board writer.** `/loop`'s load-bearing
router principle (`loop/SKILL.md:41`) forbids executing phase work. Grounding found no existing
`/loop` hand-board-write seam. So R6's intent (no hand-narrated board moves, allowlist-gated closure)
is met by `/loop` *rendering* the arc (R8) and *sequencing* to the command that owns the write
(`/work` post-merge fires the allowlisted op per R5); `/loop` does not call `board_progression` to
mutate the board. This preserves the router contract while still delivering R9's end-to-end closure.
Rejected alternative: wiring `/loop` to autonomously write the board — violates its first principle and
duplicates the write authority `/work` already owns post-merge.

**KTD4 — `project_arc` is a gate-sequence projection over lifecycle stages.** Mirroring `project_work`,
`project_arc` returns a `CardSpec(archetype="gate-sequence")` with a static superset of stages
(Idea · Plan · Work · Review · Merge · Deploy), each glyph derived purely from durable saga fields
(`lifecycle_phase`, `phase_status`, `review_paths`, `pr_refs`, `destination`) under the module's
existing SAFE-DEGRADATION rule (absent signal → NOT_REACHED). Merge/Deploy render as BLOCKED (HITL),
never auto-advanced. Consults no writable status column, board cache, or write-record ledger for its
glyphs (KD4 purity).

**KTD5 — v1 records the write; it does not roll back.** The certificate declares inverses as *data*;
executing an undo is out of scope. `board_progression` records the executed op in its ledger (enabling
a future consumer-driven rollback) but ships no rollback machinery here.

**KTD6 — `board_progression` ships a CLI and owns the concrete mission-control board_writer.** `/work`
and `/loop` are markdown skills that drive everything through `python3 …/*.py` CLI calls, not Python
imports — so the library `authorize_and_write(board_writer=…)` alone is not invokable by a skill. The
extraction therefore (a) **moves `_default_board_writer`** (the `OpKind`→`sdlc_manager.py` mapping,
`outcome.py:452`) into `board_progression` as the production writer, and (b) exposes a CLI subcommand
`write --op <op-kind> --repo <owner/repo> --number <n> --target-state <s> [--project <p>]` that resolves
that concrete writer, runs `authorize_and_write`, and prints the record JSON (`written`/`skipped`/
`gated`/`failed`) to stdout so the skill can branch (fired vs must-prompt). `outcome.py` imports both
from `board_progression` (its `:659`/`:1322` call sites unchanged via re-export). Rejected alternative:
a per-skill inline `python3 -c` snippet — unschedulable, untestable, and forks the writer.

## Implementation Units

Dependency-ordered; each independently landable and testable.

### U1 — Extract `board_progression.py` (the mechanism)

New `plugins/saga/scripts/board_progression.py`: a public `authorize_and_write(op_kind, repo, number,
target_state, *, board_writer, ledger_dir, now=time.time, max_attempts=3, payload=None)` returning one
record dict (`written` / `skipped` / `gated` / `failed` / `error`), lifting the per-op loop from
`outcome_board_sync.py:315-441`. Own `_write_once` (atomic tmp-rename) and `_safe_ledger_name` (moved
from `outcome_board_sync`, **re-exported there** so `outcome_reconcile:337` still resolves). Routes every
op through `reversibility_certificate.authorize_write`; no candidate-op derivation, no `derive_states`,
no schema. Also **move `_default_board_writer`** (`outcome.py:452`) here as the production writer, and
add a **CLI** (KTD6): `write --op <op-kind> --repo <owner/repo> --number <n> --target-state <s>
[--project <p>] [--payload <json>]` that resolves the concrete writer and prints the record JSON to
stdout (skill-invokable). `--project` defaults to `operations`.

**Test scenarios** (`tests/test_board_progression.py`, new, offline — mock certificate + board_writer):
- AUTHORIZED reversible op with absent ledger key → drives `board_writer` once, writes key, record
  `status="written"`.
- Same key present → `status="skipped"`, `board_writer` NOT called (idempotency).
- Merge/deploy op-kind (absent from registry) → `status="gated"`, no write, no key — asserted for the
  same harness call all three consumers would make (R3).
- `board_writer` raises through all attempts → `status="failed"`, no key written (retryable next tick).
- Ledger I/O fault after a committed write → `status="error"`, `may_reapply=True`, does not raise.
- Autonomous write grows only the ledger dir; no status field written anywhere (R4).
- CLI `write`: a merge/deploy `--op` prints `{"status":"gated"}` (exit 0, no writer call); an
  authorized `--op` with an injected `--runner`-style recording seam prints `{"status":"written"}`.
  (The real `gh`/`sdlc_manager` child is never exercised in tests — reuse `_default_board_writer`'s
  injected-runner seam, `outcome.py:456`.)

### U2 — Refactor `reconcile_board` to delegate (zero behavior diff)

Rewrite `outcome_board_sync.reconcile_board`'s per-op body (`:315-441`) to call
`board_progression.authorize_and_write(..., ledger_dir=_board_sync_dir(store), payload=<comment body>)`,
preserving drift-hold, schema-resolution-fail records, and the coalesced comment payload. Keep
`_board_sync_dir`, `_candidate_ops`, `_resolve_status_map`, `_parse_issue_ref`, `_default_schema_path`
in place, and re-export `_safe_ledger_name` (helper-surface preservation, KTD1). `outcome.py` imports
`_default_board_writer` from `board_progression` (re-export keeps `:659`/`:1322` call sites unchanged).

**Test scenarios:**
- `tests/test_outcome_board_sync.py` passes **unchanged**, no test-count regression (R2/AE — the
  extraction's correctness proof).
- **`tests/test_outcome_reconcile.py` passes unchanged** — proves the helper-surface preservation
  (`sync._safe_ledger_name` etc. still resolve after the extraction).
- Re-assert one representative case (gate-on-merge from the real `advance` entrypoint) still records
  `gated`, proving delegation preserved the contract.

### U3 — Add `project_arc` to `status_card.py`

New `project_arc(saga_obj) -> CardSpec` (gate-sequence), stages Idea·Plan·Work·Review·Merge·Deploy,
glyphs derived per KTD4 from durable fields. Merge/Deploy → BLOCKED. Absent signal → NOT_REACHED.

**Test scenarios** (`tests/test_status_card.py`, extend):
- Identical saga-field input with *differing* board-cache/mock state → byte-identical rendered glyph
  both times (purity / derived-on-read proof, R7/KD4/AE5).
- A saga at `lifecycle_phase=work, phase_status=complete` with `pr_refs` set → Work=DONE, Merge=BLOCKED,
  Deploy per `destination`.
- Empty/degenerate saga → all stages NOT_REACHED, constant card height (safe degradation).

### U4 — Wire `/work` post-merge (R5, KD5)

Edit `plugins/saga/skills/work/SKILL.md` post-merge section (`§4.3 :377` issue-progress + the
post-merge continuation in Phase 5): after merge, invoke
`python3 plugins/saga/scripts/board_progression.py write --op set-field-status --repo <owner/repo>
--number <n> --target-state Done` (and `--op sub-issue-close`); on `{"status":"written"}` the move
fired with no prompt, on `{"status":"gated"}` (or any non-allowlisted op incl. merge/deploy) fall back
to the existing operator-prompted `mission-control` path unchanged. Doc-only change to the skill
contract (no Python), consuming the U1 CLI (KTD6).

**Test expectation:** none — skill-doc behavior change; the enforceable contract (allowlisted fires,
merge GATEs) is covered by U1's `tests/test_board_progression.py`. (Non-feature doc unit.)

### U5 — Wire `/loop` render (R8) + KTD3 documentation (R6)

Edit `plugins/saga/skills/loop/SKILL.md`: render `project_arc` at Route / Drive / Resume entry (mirror
the `project_resume` / `project_work` header pattern already used in `resume`/`qa`/`code-review`
skills); document the KTD3 boundary (renderer + sequencer, not autonomous writer).

**Test expectation:** none — skill-doc change; `project_arc` purity is covered by U3.

### U6 — Release surfaces + drift guard

Bump `plugins/saga/.claude-plugin/plugin.json` 0.56.0 → **0.57.0** with a description note; regenerate
`.claude-plugin/marketplace.json` via `python3 scripts/sync_marketplace.py` (#429 single-source); add
`plugins/saga/CHANGELOG.md` entry (`## [0.57.0] - 2026-07-05`); update the version literal in
`tests/test_saga_plugin.py`. Run `tools/release_surface_diff_guard.py --base-ref origin/main` +
`scripts/check_release_surface_parity.py`.

**Test scenarios:** `tests/test_saga_plugin.py` version assertions pass; parity + diff-guard green.

## Scope Boundaries

**In scope:** extracting the writer mechanism; delegating `reconcile_board`; `project_arc`; wiring
`/work` (autonomous allowlisted post-merge writes) and `/loop` (arc render + sequencing); release
surfaces.

**Out of scope (true non-goals):**
- Rebuilding or relaxing the reversibility certificate (#279) or resume-time reconciliation (#295) —
  consumer-widening only.
- Widening the allowlist itself (which ops are autonomously writable) — a separate certificate change.
- Rollback/undo execution machinery (KTD5 — record only).
- `/loop` as an autonomous board writer (KTD3).

**Deferred follow-up:** a future consumer-driven rollback that reads `board_progression`'s ledger to
drive the certificate's declared inverses.

## Definition of Done

- `/work` post-merge stops prompting on allowlisted Status/close; merge/deploy still prompt.
- `/loop` renders the idea→deploy arc at Route/Drive/Resume from durable saga fields only.
- `/outcome` behavior unchanged (`tests/test_outcome_board_sync.py` green, no count regression).
- No new committed status field in any artifact touched by the diff.
- Full gate green: `uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy
  plugins/ scripts/ tests/ --ignore-missing-imports`; release surfaces in lockstep.
