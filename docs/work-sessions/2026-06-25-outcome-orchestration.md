---
title: OutcomeOrchestrator build — work session log
plan: docs/plans/2026-06-25-operator-outcome-orchestration-plan.md
review: docs/reviews/2026-06-25-operator-outcome-orchestration-plan-review.md
saga: task-outcome-orchestration
started: 2026-06-25
---

# OutcomeOrchestrator build — work session

Autonomous `/work` of the 11-unit plan, one unit per PR along the build spine, build vehicle =
**inline + ultracode assist** (operator pick; recommender said team-execution). Each unit: build inline
→ adversarial-verify via a right-sized ultracode workflow → full local gate → PR → auto-merge on green
→ next unit off updated `main`. Release-surface notes accumulate under saga's CHANGELOG `[Unreleased]`;
the version-flip + `/outcome` marketplace advertisement land at the U11 feature-flip.

## U1 — Outcome spec + DAG validation

**Built:**
- `plugins/saga/scripts/outcome_spec.py` — the canonical outcome document (KTD1): `OutcomeSpec` +
  `Node` dataclasses (superset-in-pattern of `ExecutionSpec`), per-node operational state machine in
  data (KTD2), Kahn `dependency_layers` + `ready_frontier`, `bump_revision` / atomic
  `redirect_dependency` (structural mutation → spec_revision + decision_trail, R26),
  `structural_warnings` (advisory), a `validate` that fails **before any dispatch**, and a
  `validate`/`layers` CLI.
- `plugins/saga/references/outcome-spec.md` — schema + state machine + validation-invariant reference,
  incl. the disconnection-is-advisory semantics and the `from_dict` fail-loud coercion rules.
- `tests/test_outcome_spec.py` — 47 tests across happy / edge / error / integration categories.
- `plugins/saga/CHANGELOG.md` — U1 note under a new `## [Unreleased]` section.

**Key decisions:**
- **Disconnection is advisory, not a hard failure** (revised under adversarial review). The first cut
  hard-failed a degree-0 "orphan" node when the graph had any edge. The verify panel proved that rule
  was both *too strict* (it rejected a legitimate pipeline + one independent `update-the-changelog`
  subplot) and *too loose* (it silently passed a disconnected multi-node island — the exact
  forgot-to-wire-it error it claimed to catch). Independent workstreams under one objective are
  first-class here, so disconnection is no longer dispatch-blocking; `structural_warnings(spec)` returns
  a non-fatal advisory for >1 weakly-connected component, consistently for a lone isolate and an island.
  The state-aware half of R33 (legal-edits-after-dispatch + dynamic orphan reconciliation) is U7.
- **`child_spec_ref` is a typed node field** (KTD10), never an overload of saga's `orchestration_ref`.
  U1 enforces the local, dispatch-blocking constraints (no self-recursion to the parent outcome_id, not
  the node's own id, and — added under review — no collision with a declared sibling `subplot_id`); the
  deep cross-spec ancestor-cycle check needs ancestor context and lands in U7.
- **Fail-loud type coercion at `from_dict`**: a string `depends_on`/`guarantee_tags` is rejected (not
  character-iterated into corrupted edges), `bool`/float liveness budgets are rejected (no silent 1s
  budget / truncation), and `spec_revision`/`schema_version` must be ≥ 1.
- **`redirect_dependency` is atomic**: validate-on-a-snapshot before bumping, so a rejected redirect
  never leaves a bumped revision + a decision-trail entry that lies about a rejected change (R26).
- JSON canonical (not Markdown front-matter / not SQLite) per KTD1 — deterministic round-trip, repo's
  JSON-parser tests apply.

**Requirements (honest facet scope):** U1 fully owns **R20** (validate-before-dispatch) and **R31
(validation)**, plus the **structure facet of R26** (the canonical spec container + decision-trail;
GitHub-completion + sub-issue projection are R26's other facets, in U2/U6). It ships the **spec-container
slice** of R1 (the distinct outcome-DAG data model — note `dependency_layers` is a *parallel
reimplementation* of the Kahn engine, deliberately divergent from `execution_spec`'s pilot-aware one,
not a reuse), R2 (the `leaf_saga_id`/`child_spec_ref` data seam; the coordinator-never-executes
invariant is enforced in U3), R21 (revision versioning + edge redirect; draft/prune/lazy-grow/promote
are U7), and R33 (revision versioning + the disconnection advisory; legal-edits-after-dispatch +
reconciliation are U7).

**Checks run:** `ruff format --check` ✓, `ruff check` ✓, `mypy` ✓ (no issues), `uv run pytest
tests/test_outcome_spec.py` ✓ 47 passed (96% module coverage); full suite ✓ 1013 passed (the single
local `test_suite_does_not_create_claude_dir_under_repo_root` failure is the known gitignored-saga-state
false-positive — the only leaked dir is `task-outcome-orchestration`, `git check-ignore` confirms it's
ignored and `git ls-files .claude` is empty, so it's absent in CI's clean checkout).

**Adversarial verification:** ultracode workflow (3 parallel lenses, each required to PROVE claims by
running the module standalone): validator-bypass, serialization/round-trip, requirements-honesty. **13
findings, all real except one correctly-refuted (`sort_keys=False` determinism — held across 5
`PYTHONHASHSEED=random` subprocesses).** Folded in: **P1** — `redirect_dependency` was non-atomic
(a rejected redirect left a bumped revision + a false decision-trail entry, corrupting the canonical
artifact) → now snapshot-validate-then-bump. **P2** — a string `depends_on` was character-iterated into
corrupted edges that passed `validate` → now rejected. **P2/P3** — the degree-0 orphan rule was both
too strict and too loose → replaced with the `structural_warnings` advisory. **P3s** — sibling
`child_spec_ref` collision now fails; `bool`/float liveness + negative `spec_revision` now rejected;
open pass-through maps deep-copied (detached snapshot). The requirements-honesty lens (no code bug,
fair over-claiming) drove the docstring + facet-scope corrections above and the `dependency_layers`
"reimplementation not reuse" relabel.

**Files modified:** `plugins/saga/scripts/outcome_spec.py` | `plugins/saga/references/outcome-spec.md` |
`tests/test_outcome_spec.py` | `plugins/saga/CHANGELOG.md`

**Merged:** PR #264 (squash `5e18999`). CI caught one red — `Type Check` runs `mypy plugins/ scripts/
tests/` (the whole tree, incl. tests) while the local check had only covered the one script; the
`dict[str, object]` test-fixture builders needed `dict[str, Any]`. Fixed in a follow-up commit, re-green,
auto-merged. (Memory `reference-ci-gates` updated with the full mypy scope.)

**Next step:** U2 — shared store + completion events + transition ledger.

## U2 — Shared store, completion events, transition ledger

**Built:** `plugins/saga/scripts/outcome_store.py` + `tests/test_outcome_store.py` +
`tests/test_outcome_replay.py` — the git-common-dir **cache** beside the canonical spec + GitHub
(KTD15). The store is the durability/coordination substrate the plan reviewers all flagged as
under-defined; this unit makes every primitive concrete and runnable.

**What it ships:**
- **`Store` + git-common-dir resolution** (R27): `git rev-parse --git-common-dir` → the same absolute
  store root from every worktree; injectable `runner` so it's testable with no real git repo.
- **Completion events** (R9/R10/R28): immutable write-once JSON per leaf per attempt (`os.link`), so two
  leaves finishing at once never contend; idempotency-key dedup, with a genuine new-`attempt` retry
  proceeding to its own file. `completed_subplots` feeds U1's `ready_frontier`.
- **Atomic writes + quarantine** (R30): `os.replace` for mutable files (no torn read); a malformed file
  is moved to `quarantine/` and skipped, never fatal.
- **Replay ledger** (R30): append-only `O_APPEND` JSONL tolerating a torn **trailing** line (a mid-file
  malformed line is real corruption → raises); `replay_pending` pairs intents to commits by idempotency
  key so a crash *after* a side effect but *before* its commit re-drives without duplicating (composes
  with completion-event idempotency).
- **Leases** (R13): lease-based `coordinator` lock (a second `advance` no-ops on a held lease, reclaims a
  stale one) + per-subplot dispatch locks (no duplicate dispatch); injectable `now`.
- **Offline queue** (R34, made concrete): GitHub wins for completion → a server-superseded queued write
  is **dropped** (not replayed); a retry budget pages the operator on exhaustion instead of looping.

**Key decisions:**
- **Write-once via temp + `os.link`** (atomic create that refuses to clobber) for completion events,
  separate from temp + `os.replace` (overwrite) for mutable files — the immutability vs atomicity split.
- **Torn-tail tolerance is a precise allowance**, not "skip bad lines": only a malformed *trailing*
  ledger line is dropped; a mid-file bad line raises (genuine corruption, not a crash tail).
- **`runner`/`now` resolved at call-time** (None-sentinel default, not a bound default arg) so the CLI
  path is monkeypatch-testable offline — fixed after the first cut bound `subprocess.run` at def-time.
- **GitHub is authoritative for completion**: the cache holds nothing canonical, so blowing it away
  (`git worktree remove`, a wipe) loses nothing — reconcile rebuilds from spec + GitHub.

**Requirements (honest facet scope):** U2 ships the **cache + durability + coordination** facets of
R9/R10/R13/R27/R28/R30/R34. The parent-owned **barrier predicate** (R9) lands in U5; real GitHub reads +
**export/import** (R14) and the auto-merge/negative-state side of R30/R34 land in U5/U6/U7. U2 has no
network and no coordinator runtime by design (that's U3+).

**Checks run:** `ruff check .` ✓, `ruff format` ✓, `mypy plugins/ scripts/ tests/ --ignore-missing-imports`
✓ (72 files), `pytest tests/test_outcome_store.py tests/test_outcome_replay.py` ✓ 34 passed
(`outcome_store.py` 90%); full suite ✓ 1047 passed (+ the same known local false-positive).

**Adversarial verification:** ultracode workflow `verify-outcome-u2` (3 lenses: concurrency/atomicity,
durability/replay, requirements-honesty), each proving claims by running the store standalone with real
threads + clock injection + crash sequences. Two genuine **P1s** + several P3s; several attacks
correctly refuted. Folded in:
- **P1 (concurrency)** — under a concurrent *identical-key* delivery, the `os.link` loser raised (with a
  self-contradictory `key K != K` message) instead of deduping. Now the loser compares keys and returns
  `"skipped"` when they match, raising only on a genuine divergent-completion conflict.
- **P1 (durability)** — the ledger's torn-tail tolerance was read-only, not self-healing: a post-crash
  append merged into the broken line (first append lost) and a second *bricked* `read_ledger` forever.
  `append_ledger` now `_heal_torn_tail`s (truncates the unterminated fragment) before writing and loops
  on short writes — the exact R30 crash now survives an append.
- **P2** — `_atomic_write`'s pid-only temp name collided across same-process threads → now pid + thread
  id + monotonic nonce (shared `_unique_tmp`, mirroring `_write_once`).
- **P3s** — a non-object mid-file ledger line now raises (was silently skipped); `completed_subplots`
  makes **success sticky** (a later `failed` attempt no longer un-completes a `done` leaf — it removed
  the latest-attempt-wins logic); the offline queue gained real **exponential backoff** (`next_retry_at`
  consumed by `drain_offline`, which now defers not-yet-due entries) so R34's "exponential backoff, cap
  N" is genuinely delivered, not just the cap.
- **Honesty (P2/P3)** — the lease-reclaim TOCTOU is documented as best-effort with dispatch-lock +
  idempotency as defense-in-depth (a fencing token is deferred to U6's coordinator — adding it now with
  no consumer would be dead-wiring); R9/R14/R27/R28 facet scoping clarified (U2 ships the cache/durability
  facets; barrier predicate → U5, export/import → U3/U7, GitHub-read reconstruct leg → U5). The
  cache-loss test comment was rescoped to "cache holds no canonical state" with the GitHub-read leg
  flagged as U5.

**Correctly refuted (no change):** lease held-vs-stale boundary, `replay_pending` set-logic,
crash-after-effect-no-duplicate, quarantine-stops-tripping-reads, and that R10/R13/R30/R34-policy are
genuinely satisfied + tested (not name-dropped).

**Files modified:** `plugins/saga/scripts/outcome_store.py` | `tests/test_outcome_store.py` |
`tests/test_outcome_replay.py` | `plugins/saga/CHANGELOG.md` | `docs/engineering-journal/DECISIONS.md`

**Merged:** PR #265 (squash `db16773`). CI green first try — the U1 full-tree-mypy lesson held.

**Next step:** U3 — thin `/outcome` command + local reconcile skeleton.

## U3 — Thin `/outcome` command + reconcile skeleton

**Built:** the OutcomeOrchestrator coordinator surface + engine, composing U1 (spec) + U2 (store):
- `plugins/saga/scripts/outcome.py` — the **reconcile engine**: `start` / `resume` / `advance`
  (`--loop`) / `attend` / `status` / `graph` / `export` / `import`, plus the derived-state computer.
- `plugins/saga/commands/outcome.md` + `plugins/saga/skills/outcome/SKILL.md` — the thin operator
  surface (KTD11 coordinator verbs; leaf work stays the native verbs).
- `tests/test_outcome_command.py` — 15 tests across the U3 scenarios + the two invariants.

**Two invariants enforced structurally:**
- **The coordinator routes, never executes (R2/R3).** `advance` only calls the injected `dispatcher`
  (record-only by default; real backends are U4/U9) and reads completion events — it never runs a
  leaf's work in-process. The test proves design dispatches to `dispatched` (not `done`) with no
  completion event fabricated.
- **Status is derived on read (R17).** A node's live state is computed every call from spec +
  completion events + dispatch records; there is no stored status field (the spec has none). A
  completion event written directly to the store flips the derived state with no `advance` and no
  status write.

**Key decisions:**
- **Node operational state is derived, not committed per tick.** The committed spec carries
  structure (not churning per-tick state), so branch history stays clean (the R21-grows-lazily vs
  R26-committed cadence tension); live state = completion events (store) + dispatch records (ledger),
  recomputed each tick (R29 level-triggered). This is the cleanest reading of R17/R29 and avoids
  per-dispatch commits.
- **Dispatch dedup = per-subplot lock (concurrent-tick guard) + durable ledger record (idempotent
  skip).** Repeated `advance --once` never double-dispatches; a second concurrent `advance` no-ops on
  the held coordinator lease (released in a `finally`, so a raising dispatcher can't brick the loop).
- **The command surface lands in U3 (per the plan file list) with full model + manual + guard-count
  integration**, but the generated command-matrix visual stays at the released 18 (the renderer uses a
  hardcoded command list, so adding `/outcome` to the model changes no SVG) and the marketplace version
  flip + advertisement stay deferred to U11. `/outcome` is in the source + dogfoodable now; it is not
  *released* until U11.

**Requirements (honest facet scope):** U3 owns **R16** (thin surface) and **R29** (level-triggered
reconcile), and ships the **dispatch-seam** facet of R1/R2/R3 (the coordinator-never-executes contract;
the degrade-only-leaves half of R3 lands in U9) and the cockpit facet of R17 (full report + attention
consolidator are U8). R1's literal "reuse `execution_spec`/`recommend_execution_backend`/`save`" — U3
reuses the U1 frontier engine (itself a deliberate Kahn reimplementation) and the U2 store, not
`saga.py`'s tick model; the recommender wires in at U9.

**Checks run:** `ruff check .` ✓, `ruff format` ✓, `mypy plugins/ scripts/ tests/` ✓ (73 files),
`pytest tests/test_outcome_command.py` ✓ 15 passed (`outcome.py` 93%), saga guards
(`test_saga_plugin` + `test_saga_docs_coverage`) ✓ 40 passed; full suite ✓ 1068 passed; plugin
validators ✓.

**Adversarial verification:** ultracode workflow `verify-outcome-u3` (3 lenses: coordinator-invariant,
derived-state-fidelity, requirements+surface-honesty), each proving claims by running the engine
standalone with re-entrancy, crash injection, and multi-graph state probes. The R3 invariant, lease
`finally`, loop bounding, derive precedence, derived-each-call status, and cross-repo bundle fidelity
all held; the surface wiring is CI-green. Folded in:
- **P2 (concurrency)** — the default `holder="coordinator"` constant gave zero mutual exclusion (the
  same-holder lease just *refreshes*), so a re-entrant/concurrent `advance` double-dispatched a leaf.
  Now `holder` defaults to a per-invocation unique id (`coordinator-<pid>-<nonce>`) → a concurrent
  advance is a different holder and genuinely no-ops on the held lease.
- **P3 (durability)** — dispatch was recorded as a single `intent` (no `commit`), so a post-dispatch
  `append_ledger` failure re-launched the leaf and `replay_pending` flagged every dispatch forever. Now
  dispatch is **intent → effect → commit** (the store's replay protocol); dedup keys on `commit`, so a
  failed dispatch is re-drivable and settled dispatches are skipped.
- **P2 (cockpit)** — a negatively-terminated leaf (failed/rejected/stalled) rendered forever as
  `dispatched` (a dead leaf looked in-flight). `derive_states` now surfaces the actual terminal state;
  the dead `LIVE_PENDING` branch was removed (it was unreachable — frontier ≡ ready).
- **P3** — re-import doubled the dispatch ledger → now deduped by `(phase, key)`.
- **Honesty (P2/P3, no code)** — softened the `resume` docstring: in U3 completion is cache-resident and
  a wipe *does* drop it (GitHub reconstruction is U5; `export` is the durable checkpoint until then).
  R1's "reuse saga machinery" is honestly a reimplementation (already disclosed; `recommend_execution_backend`
  reuse lands at U9); KTD11's `report`+`close` verbs are deferred (U8/later) and `status` is an extra
  read-half-of-report verb — all disclosed in the surface and CHANGELOG.

**Files modified:** `plugins/saga/scripts/outcome.py` | `plugins/saga/commands/outcome.md` |
`plugins/saga/skills/outcome/SKILL.md` | `tests/test_outcome_command.py` |
`plugins/saga/docs/model/saga-docs-model.yaml` | `plugins/saga/docs/commands.md` |
`tests/test_saga_plugin.py` | `tests/test_saga_docs_coverage.py` | `plugins/saga/CHANGELOG.md` |
`docs/engineering-journal/DECISIONS.md`

**Next step:** U4 — team-execution backend + R8 cleanup (DESTRUCTIVE: delete `team-setup`, strip ~60
tmux refs from team-execution; update the asset-reference guard test in the same PR).

## U4 — Team-execution backend + R8 cleanup (DESTRUCTIVE)

**Built (two halves):**
1. **The dispatcher seam** (R5/R6/R23) — `plugins/saga/scripts/outcome_dispatcher.py` +
   `tests/test_outcome_dispatcher.py`: the single seam every subplot routes through. `dispatch(req)`
   either mints a leaf saga id + a `/resume` return channel (R9 re-entry token out) or, when the chosen
   backend cannot run, returns a **HALT-not-degrade receipt** (`HaltReceipt`); `make_dispatcher` is the
   `Dispatcher` for `/outcome advance` (HALT raises `BackendHaltError`, never a silent substitute).
   **team-execution is the first real backend** (R6); the rest of the menu HALTs until U9. Wired
   `team_emitter` as the **third leg of `recompile_for_tier`** in `execution_spec.py` (team-execution
   mode → `## Team Structure` markdown, not the inline baseline — R5) with a new degrade test.
2. **The R8 reshape of team-execution** (bumped to **2.2.0** — plugin.json + marketplace + CHANGELOG):
   deleted `commands/team-setup.md` (whole command), `docs/example_tmux.conf`, `docs/agent-overflow.sh`,
   and `skills/.../references/validator-pane-behavior.md`; stripped tmux from README + SKILL.md +
   `team_emitter._REFERENCE_FILES`. **Zero tmux refs survive outside the team-execution CHANGELOG
   history** (the unrelated redis-channel tmux-foreground note is a different plugin, left alone). The
   `.claude/`-git-ignored **validator-state safety check was re-homed** into a new Phase B preflight
   (Step B0a) so it survives the `/team-setup` deletion — it now runs in BOTH Phase A (Step A5) and
   Phase B preflight; `validator-evidence-state.md` stays the state-location contract.

**Key decisions:**
- **HALT is encoded as the absence of a fallback path, not a runtime flag.** `dispatch` has no code
  branch that substitutes inline for an unavailable backend — an unavailable backend *always* yields a
  receipt, so "never silently substitute" (R5/R23) is structural and testable (every NODE_BACKEND
  parametrized). The operator-presence degrade-vs-halt *decision* (R23) is U9; U4 owns only the receipt.
- **The `recompile_for_tier` 3rd leg is the explicit R5 correction** (`outcome_spec.py:88` already flagged
  it as awaited). Safe: no test pinned `team-execution` → inline baseline (only inline / cc-workflows /
  unknown-tier are pinned), so wiring `team-execution` → `team_emitter` is additive; the inline/workflow/
  downgrade-floor paths are unchanged. Lazy import-by-path avoids the `execution_spec ↔ team_emitter`
  cycle.
- **KTD13 — the deletion carries its own guard.** Replaced `test_team_setup_references_existing_assets`
  (which pinned the now-deleted tmux assets) with `test_team_setup_and_tmux_assets_are_removed`, which
  fails if any deleted asset returns OR any tmux ref is reintroduced outside CHANGELOG.
- **KTD14 — team-execution carries its own 2.2.0 triad bump in this PR** (not deferred to U11), so the
  release-triad guard stays green at this interim merge.

**Requirements (honest facet scope):** U4 ships **R8** (full reshape) and **R5** (the seam + team_emitter
wiring), the **R6 first-backend** slice (team-execution; the full menu is U9), and the **R23 HALT
receipt** (the degrade-one-rung-vs-halt operator-presence decision is U9). The R7 recommender is U9.

**Checks run:** `ruff check .` ✓, `ruff format` ✓, `mypy plugins/ scripts/ tests/` ✓ (74 files),
`pytest tests/test_outcome_dispatcher.py` ✓ 15 passed (`outcome_dispatcher.py` 96%), team-execution +
release guards ✓ 53 passed, degrade tests ✓ 38 passed; full suite ✓ 1086 passed; validators ✓.

**Adversarial verification:** ultracode workflow `verify-outcome-u4` (3 lenses: R8-cleanup-completeness,
dispatcher+recompile, requirements+release-surface), each proving claims by running grep/pytest + the
modules standalone with crash injection. R8 removal verified clean; HALT-never-silent-substitute,
no-degrade-regression, closed-vocab rejection, and the team_emitter wiring all held. Folded in:
- **P1 (lock leak)** — a HALTed leaf leaked its per-subplot dispatch lease, so the HALT was *silently
  masked* on every re-tick for the 900s TTL. Now `_reconcile_once` **catches the HALT per leaf**,
  releases the dispatch lock, records the receipt in the ledger, and re-surfaces it on the next advance.
- **P2 (tick starvation)** — one HALT leaf aborted the whole reconcile tick (raised out of `advance`),
  starving independent runnable leaves. Now the loop **continues** past a HALT; `AdvanceResult.halted`
  carries the receipts. Regression tests pin both (re-surfaces each advance; a runnable leaf dispatches
  despite a sibling HALT).
- **P2 (R5 not actually wired)** — `make_dispatcher` was never wired into the production `/outcome
  advance` (it still used the U3 record-only default), so the CHANGELOG overclaimed. **The advance CLI
  now routes through the real seam**; the record-only dispatcher is the test fallback only.
- **P3** — softened `recompile_for_tier`'s docstring (the team-execution leg renders roles, not per-unit
  `{model,effort}`). Strengthened the R8 guard to also fail on a dangling `validator-pane-behavior`
  reference (the gap that hid the clobber damage below).
- **P2 (CHANGELOG overclaim)** — narrowed "no tmux remains" to **in this plugin**: three pre-existing
  repo-root tmux dev scripts under `docs/` are out of R8's plugin charter (the plan's tmux count was
  plugin-scoped). Left them untouched (scope discipline) rather than expand U4 into unrelated files.

**⚠️ Review incident (recovered).** A verify agent ran `git checkout SKILL.md` during a guard
mutation-test, which **clobbered the uncommitted U4 SKILL.md** (the changeset wasn't committed yet) and
left an imperfect reconstruction (`validator-pane-behavior.md` reappeared in Step A4). Recovery was
**deterministic, not trusting the reconstruction**: `git checkout HEAD -- SKILL.md` to the clean U3
base, then re-applied the exact 5 U4 edits; `git diff HEAD` confirms only the intended changes (A0b
removed, both pane refs gone, Step B0a added, tree entries removed). **Lesson → memory + journal:
commit/stash a changeset before launching an adversarial-verify** (the agents have write+bash and can
run destructive git on an uncommitted tree). Design fix to encode it: the HALT-contract class lives in
`outcome_dispatcher` (never `__main__`) so the engine's `except` and the dispatcher's `raise` reference
the same class regardless of launch path.
