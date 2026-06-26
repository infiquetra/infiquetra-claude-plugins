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

## U5 — Completion barrier + recursive child outcomes

**Built:** `plugins/saga/scripts/outcome_github.py` (read-only GitHub PR/issue state) +
`plugins/saga/scripts/outcome_orchestrator.py` (the parent-owned barrier) + `tests/test_outcome_completion.py`
(12 tests). This is the **GitHub-canonical completion** leg the U2/U3 honesty passes explicitly deferred
to U5.

**What it ships:**
- **`outcome_github`** (R10/R27/R34): `pr_state` (merged/closed/open/unknown) + `issue_state`
  (closed/open/unknown), via `gh` with an injectable runner. Every read **degrades to `unknown`** on a
  `gh` failure — a `merged` requires a real `mergedAt`, so a closed-unmerged PR reads `closed` (R32),
  never `merged`. A GitHub outage can only DELAY an unlock, never fabricate one.
- **`barrier_satisfied`** (R9/R11): the parent's predicate over evidence — code=PR-merged,
  non-code=closed-tracking-issue (or a `canonical`-flagged event for untracked work), child=child
  terminal-successful (KTD10 recursion via an injected reader). Returns a `BarrierVerdict` that HALTs
  (satisfied=False, with the reason + evidence) on an unmet contract.
- **`harvest`** (R10): runs the barrier over the spec each tick and materializes each newly-satisfied
  contract as a success completion event in the store → the existing `completed_subplots` frontier read
  unlocks the next Kahn layer. Idempotent; a cache-less machine re-harvests from GitHub (R27 — tested:
  wipe the store, re-harvest, the closed-issue completion comes back).
- **`blocked_subtree`** (R22): only a hard-blocked node's downstream subtree pauses; independent
  siblings keep running.
- Wired into `advance` as an optional injected **`harvester` hook** (runs before the frontier read each
  tick); `AdvanceResult.harvested` surfaces what was materialized.

**Key decisions:**
- **Completion is GitHub-canonical, the cache is a materialization.** The barrier reads canonical truth
  from GitHub (PR merged / issue closed); `harvest` writes it into the store cache. This makes the
  frontier logic (which reads the cache) GitHub-backed AND keeps the cache-loss-loses-nothing property
  (R27) real — a wiped cache is re-harvested from GitHub. This closes the honest gap the U2 cache-loss
  test flagged ("the GitHub-read reconstruct leg is U5").
- **The barrier is the parent's predicate over evidence (R9), encoded as a verdict object** carrying
  the contract + the canonical state + the evidence, so a HALT is explainable (the report/U8 shows
  *why* a leaf isn't done) and re-verifiable — never a child's self-asserted "done".
- **`unknown` is the safe degraded value** everywhere — a GitHub read failure is never coerced to a
  completion. Only `merged`/`closed` (positive) unlock; `unknown`/`open` hold.
- **Harvest is success-only in U5.** Negative-terminal harvest (a closed-unmerged PR → `rejected`
  cascade) is U6 (GitHub negative states + auto-merge); U5 unlocks on success.

**Requirements (honest facet scope):** U5 owns **R9** (barrier predicate), **R10/R11** (completion
contract + Kahn unlock), **R22** (cascade), and the **R27/R28 GitHub-read completion leg**. The merge
*action* (R12) + negative-state handling (R32) land in U6; U5 only *reads* completion truth.

**Checks run:** `ruff check .` ✓, `ruff format` ✓, `mypy plugins/ scripts/ tests/` ✓ (75 files),
`pytest tests/test_outcome_completion.py` ✓ 12 passed; full suite ✓ 1101 passed; validators ✓.

**Adversarial verification:** committed first (per the U4 lesson — the verify prompt also forbade
destructive git on the working tree), then ultracode workflow `verify-outcome-u5` (3 lenses:
barrier+GitHub-safety, harvest+cache-less+cascade, requirements-honesty), each proving claims by running
the modules standalone with injected fake `gh` runners + crash injection. **The false-unlock / degraded-
read attacks were all refuted** — every `gh` failure mode degrades to `unknown`, a closed-unmerged PR
reads `closed` not `merged`, the barrier HALTs per-kind correctly, and no child can self-report (harvest
is the sole success-event writer). Folded in:
- **P1 (loop wedge)** — `harvest` hardcoded `attempt=1`, so a subplot holding a prior `failed`/`rejected`
  terminal at attempt 1 collided → `OutcomeStoreError` propagated out of `advance` and wedged every
  future tick. Now it materializes at `max(attempt)+1`; regression test pins it.
- **P2 (dead-wiring, same class as U4)** — the production `/outcome advance` never passed a `harvester`,
  so U5 was inert in the live loop and "wired into advance" overclaimed. Now a `production_harvester`
  (with the recursive, cycle-guarded child-outcome reader, KTD10) is wired into the CLI; an
  advance→harvest→unlock→dispatch end-to-end test + a child-recursion test pin it.
- **P3 (honesty)** — corrected the contradictory "canonical event recorded in the committed spec"
  claim: the untracked-non-code canonical event is **cache-resident** (lost on wipe), NOT cache-less;
  the tracked-issue path is the cache-less one. Softened "U5 ships R9" to the **barrier-predicate half**
  (the re-entry-token-out is U4's dispatch).

**Refuted (no change):** GitHub-read fail-safety (R34), per-kind barrier HALT correctness, parent-
ownership (no child self-report), harvest idempotency, `blocked_subtree` exactness, and that U5 does NOT
overreach into the merge action / negative-state handling (correctly U6).

## U6 — Auto-merge queue + GitHub negative states

**Built:** `plugins/saga/scripts/outcome_merge.py` (the queue + negative cascade) +
`plugins/saga/scripts/outcome_github.py` write side + `tests/test_outcome_merge_queue.py` (16 tests).
This is the auto-merge **action** + the negative-state handling U5 deferred (U5 only *read* completion).

**What it ships:**
- **`outcome_github` write side** (R32/R34): `base_ref_oid` / `merge_state` (clean/behind/blocked/dirty)
  / `squash_merge` / `update_branch` / `branch_exists`, all via `gh` with an injectable runner. Every
  one **degrades to a safe value** (empty SHA / `unknown` / `conflict` / branch-present) so a `gh`
  outage defers or fails-safe, never performs a wrong merge or falsely rejects a live branch.
- **`auto_merge_one`** (R12): the guarded rebase-reverify-squash loop. Out-of-band/negative checks
  FIRST (already-merged → no duplicate; closed-unmerged / deleted-branch → `rejected`, R32);
  gated/risky/destructive → wait for operator; `behind` → rebase + re-verify; the squash is guarded by
  an **expected base SHA** (a manual merge landing during re-verify → `base-changed` → reloop, never a
  stale-tree merge); base churn **capped at 3** → halt + page; a conflict → fail the leaf back to
  `work` + page.
- **`process_merge_queue`** (R12/R22/R32): serializes the eligible code leaves (one squash at a time —
  two siblings can't both merge on stale bases), records `rejected`/`failed` negative terminals, and
  returns the **cascade** (`blocked_subtree` over the rejected set — only their downstream pauses).
- GitHub ops injected as a `MergeOps` adapter (`github_merge_ops` wires the real `gh`), so the whole
  queue is unit-tested offline.

**Key decisions:**
- **The squash is SHA-guarded, not just freshness-checked.** A base-freshness check alone races a
  manual merge landing during re-verify; the expected-base-SHA guard (re-read the base tip right before
  merging, reloop if it changed) is what makes "never merge a stale tree" hold under concurrency
  (R12/R30). The cap (3) turns an adversarial base-churn from a spin into a halt+page.
- **Negative terminals cascade like a block (R22), and are recorded as sticky terminal events.** A
  `rejected`/`failed` is written to the store at a fresh attempt (the U5 attempt-fix pattern), so the
  frontier sees the leaf as not-success and its downstream pauses — dependents never hang on a dead PR.
- **Safe-degrade everywhere on the write side too.** `branch_exists` returns *present* on an
  indeterminate read (a flake must not falsely reject a live subplot); `squash_merge` non-zero is a
  `conflict` (leaf → work), never a silent skip.

**Requirements (honest facet scope):** U6 owns **R12** (the auto-merge queue) + **R32** (PR/branch
negative terminals) + the **R22 negative cascade** + **R30** (the SHA-guarded merge atomicity). The
**worktree-removed** terminal is U7; the offline merge-queue reuses U2's `enqueue/drain_offline`
(GitHub-wins) — `outcome_merge`'s own degraded-safe reads cover the read side here.

**Checks run:** `ruff check .` ✓, `ruff format` ✓, `mypy plugins/ scripts/ tests/` ✓ (76 files),
`pytest tests/test_outcome_merge_queue.py` ✓ 16 passed; full suite ✓ 1120 passed; validators ✓.

**Adversarial verification:** committed first (per the U4 lesson; verify prompt forbade destructive
git), then ultracode workflow `verify-outcome-u6` (3 lenses), each running the modules standalone +
the REAL `github_merge_ops` with an injected failing `gh`. The base-churn cap, cascade exactness, and
negative-state classification were refuted (correct). A cluster of real defects — all pointing at the
same root (the fake-CAS guard + a non-representative test) — folded in:
- **P1 (R34 violation)** — a `gh` outage made `merge_state`→`unknown` fall through to a squash, and
  `squash_merge` returned `"conflict"` on *any* non-zero exit → a permanent `failed` terminal. The unit
  test masked it with `squash="error"`, a value the real adapter could never emit. **Fix:** GitHub is
  now the authoritative guard — `squash_merge` returns `merged`/`error` (conflicts are detected via
  `merge_state="dirty"`), `unknown`/unreadable-base → **defer** (`not-ready`), never a terminal. A
  real-adapter regression test (failing `gh` → defer, no terminal recorded) replaces the masked one.
- **P2 (fake CAS)** — the "expected-base-SHA guard" was two adjacent reads with the SHA never bound to
  the merge — a base change after the read still squashed a stale tree. **Fix:** dropped the local
  double-read; GitHub is the atomic guard via `--match-head-commit` (it rejects a moved-head/behind PR),
  and a rejected squash reloops.
- **P2 (conflict-recovery deadlock)** — the skip-set used `successful_only=False`, so a `failed`
  (conflict) leaf was skipped forever even after /work fixed it. **Fix:** the skip-set is success ∪
  `rejected`/`stalled`; `failed` is retryable (regression test: conflict → fixed → re-merged).
- **P2 (dead-wiring + no cross-process serialization, same class as U4/U5)** — `process_merge_queue`
  was never wired into `advance`. **Fix:** wired as a `merge_processor` hook run under the held
  coordinator lease → single-writer cross-process (R13).
- **P2 (`branch_exists` can't see a real 404)** — returned `True` on every non-zero. **Fix:** a definite
  `404`/`not found` in stderr → gone; transient → present.
- **P3 (honesty)** — corrected the offline claim (it's **defer-and-retry** via safe-degrade, not the U2
  enqueue/drain queue) and noted the gate-evidence (CI-green/review) is enforced via GitHub's
  `mergeStateStatus=blocked`, not re-run by the coordinator.

**Refuted (no change):** base-churn cap exactness, `blocked_subtree` cascade exactness, out-of-band /
closed-unmerged classification, rejected-terminal idempotency, and that U6 does NOT overreach into the
worktree terminal (U7) or degrade decision (U9).

## U7 — Decomposition, graph editing, worktree lifecycle

**Built:** `plugins/saga/scripts/outcome_decompose.py` (graph editing + approval gate + orphan
reconcile) + `plugins/saga/scripts/outcome_worktrees.py` (the durable per-sub-outcome worktree
lifecycle + the worktree-removed terminal) + `tests/test_outcome_graph_edit.py` (23 tests) +
`tests/test_outcome_worktrees.py` (19 tests). Wiring in `outcome.py` (`worktree_processor`,
`gate_factory`, the `approve`/`prune`/`promote` verbs, `AdvanceResult.worktrees`/`.gated`).

**What it ships:**
- **Graph editing** (R21/R33): `add_node`/`add_dependency`/`remove_dependency`, `lazy_grow` (append a
  later layer as evidence arrives), `elaborate` (splice a node into sub-nodes — entries inherit its
  upstream, dependents rewire onto the sinks), `promote` (set `child_spec_ref`, rejecting a point-back at
  this/any ancestor outcome — the cross-spec cycle guard U1 deferred), `prune`. Each is **atomic**
  (snapshot → validate → bump revision + decision-trail; a rejected edit leaves the spec untouched) and
  **state-aware** (a `dispatched` node can't be pruned/elaborated — terminal transition first, R33).
- **Orphan reconciliation** (R33): a prune drops every edge to the node, **closes its generated
  sub-issue** (injected `issue_close`; U8 makes the ref), **reaps its worktree** — runs *after* the
  canonical prune commits, so a rejected prune never closes a live issue.
- **Approval gate** (R20): `approve_frontier` / `frontier_approved` / `make_dispatch_gate`, keyed by
  `spec_revision` — a structural edit re-closes the gate; the gate sits upstream of the backend HALT.
- **Worktree lifecycle** (R15): `ensure_worktree` (one per sub-outcome, reused across leaves, cap-defer,
  owner-tagged, shared `shared_install_ref`), `reap_worktree`, `provision_pending`, and
  `harvest_worktrees` (reap terminals + the R32 **worktree-removed → `rejected` + R22 cascade**). git is
  the liveness oracle via the injected `WorktreeOps` (`git_worktree_ops` wires real `git worktree`,
  degrade-safe `exists` → present on a flake).

**Key decisions:** (full rationale → DECISIONS `#outcome-decompose-worktree-stance`)
- **Worktrees are per-SUB-OUTCOME, not per-leaf** — only `is_outcome` nodes are managed; the worktree is
  the per-node unit the R32 removed-terminal attaches to.
- **git is the liveness oracle** (the U6 lesson) — existence read from `git worktree list`, registry holds
  only owner/branch/shared-install; a transient git failure degrades to present (R34).
- **The cap defers, never overshoots** — past N, provisioning returns `capped` (page-and-wait).
- **Every edit atomic + state-aware**; **approval per-revision** ties R20 to R33's versioning.

**Requirements (honest facet scope):** U7 owns **R13** (subplot-id/worktree namespacing) + **R14** (the
graph edits keep the spec round-trippable/portable — export/import is U3) + **R15** + **R20** + **R21** +
**R32-worktree** (the terminal U6 deferred) + **R33**. The sub-issue *generation* is U8; the pruned-node
**cost** reconcile is U10.

**Checks run:** `ruff check .` ✓, `ruff format --check` ✓, `mypy plugins/ scripts/ tests/` ✓ (78 files),
`pytest` two U7 files ✓ 42 passed; full suite ✓ (1 local-only `.claude/`-dir guard deselected, green in
CI); validators ✓.

**Adversarial verification:** committed first (per the U4 lesson; every verify prompt forbade
destructive git + editing `plugins/`/`tests/`), then ultracode workflow `verify-outcome-u7` — 6
refutation lenses (cap/liveness, R34 degrade, state-aware edits, atomicity/rollback,
elaborate-splice/promote-cycle, gate/dead-wiring) + a synthesis judge, each running the modules
standalone against a real temp store (and a real `git` repo for the adapter). **Atomicity/rollback across
all six edit ops, the approval gate + dead-wiring (all three hooks reached by the production wiring), and
strict R33 ('dispatched' rejection) were heavily attacked and HELD.** One **P0** (independently
constructed by three lenses) + two P2 + four P3 folded:
- **P0 (R15 + R34, the real-adapter path mismatch)** — `git_worktree_ops` compared the registry path
  **verbatim** against `git worktree list --porcelain`'s **absolute, realpath-canonical** paths, while
  the registry stored the path built from an **un-resolved** `repo_root` — and the `/outcome` CLI
  defaults `--repo-root .`. Reproduced against a real git repo: a freshly-created, on-disk-present
  worktree read `ops.exists()==False`. From that single false-ABSENT, **both** guarantees broke
  deterministically: R15 (`live_worktrees` empty → the cap never trips → unbounded fan-out) and R34
  (`harvest_worktrees` saw a live non-terminal node as "definitely absent" → drove it to the sticky
  `rejected` terminal that cascades — silently killing live sub-outcomes on the *second advance tick of
  every real default run*). The all-fake unit tests structurally could not catch it (the fake keys on the
  identical string; the real-adapter tests hand-fed matching porcelain listings). **Fix:** canonicalize
  both sides — `git_worktree_ops` resolves `repo_root` once and reduces every path to
  `realpath(join(resolved_root, path))`; the CLI resolves `--repo-root` to absolute. New **real-git
  regression test** provisions a worktree under a **symlinked root** and asserts the live worktree reads
  PRESENT, harvest does not terminate it, and the cap is enforced.
- **P2** — `reap_worktree` swallowed a failed `ops.remove()` and deregistered anyway → a stuck worktree
  silently leaked from the cap accounting. **Fix:** honor the bool — a failed removal keeps the entry
  (retried next pass); a `reap_failed` list surfaces it.
- **P2** — `harvest_worktrees` skipped a registry entry whose node had left the spec (`node is None`) →
  the orphan held a cap slot forever. **Fix:** reap node-gone orphans (an `orphaned` list).
- **P3** — `elaborate` doubled an inherited upstream edge (dedup); the elaborate-on-terminal rejection
  message said "transition it to terminal first" on an already-terminal node (split the message); the
  prune docstring's "never silently discard" framing collided with `failed`=returns-to-work (clarified:
  pruning a terminal `failed` leaf is explicit operator abandonment, not silent); the `promote`
  ancestor-cycle guard is unreachable from the CLI (no nested-outcome context yet — documented the
  deliberate deferral + the runtime `seen`-guard that prevents actual infinite recursion).

**Refuted (no change):** atomicity/rollback of all six ops, the approval-gate re-close + advance
integration (gate, worktree_processor, dispatch_gate all reached by production wiring — no dead-wiring),
strict R33 'dispatched' rejection, the provisioning-lags-dispatch-by-one-tick (by design, level-triggered),
and a non-`OutcomeSpecError` escaping the rollback (not constructible — `from_dict` coerces pre-mutation).

## U8 — Reporting, attention consolidator, mission-control projection

**Built:** `plugins/saga/scripts/outcome_report.py` (the consolidator + the derived-on-read report) +
`plugins/saga/scripts/outcome_projection.py` (the mission-control secondary projection) +
`tests/test_outcome_report.py` (10) + `tests/test_outcome_projection.py` (6) + a committed generated
example under `docs/outcomes/_example-ship-auth/`. Wiring in `outcome.py`: `report` / `project` verbs + a
consolidated `attend` (no subplot → the ranked prompt).

**What it ships:**
- **Attention consolidator** (R18/AE5/F3): `consolidate(spec, store)` → ONE ranked prompt, **type-tier
  first** (gate → ambiguity → failure) then **unblock-leverage** (`len(blocked_subtree({sid}))`) within a
  tier. Each node is classified into exactly one kind (failure = terminal-negative, ambiguity = HALT
  receipt, gate = gated/risky/destructive + dispatched); a healthy steady state → empty surface.
- **Report** (R19/F6): `report_markdown` / `write_report` overwrite `docs/outcomes/<id>/report.md` from
  state — Mermaid topology, the consolidated prompt, a per-subplot state+evidence+cost table, the cost
  rollup ("no data yet" when absent), the decision trail. **Deterministic** (no wall-clock) so it cannot
  drift.
- **Projection** (R25): `project(spec, store)` → the mission-control secondary view, generated from state
  (no operator-writable status), `parent_close = operator-keystroke-only` (never auto-closes the parent).

**Key decisions:** (full rationale → DECISIONS `#outcome-report-projection-stance`)
- Everything **derived-on-read** (R17), no operator-writable status — the cockpit can't lie.
- The report is **deterministic + overwrite-from-state** so it physically cannot drift.
- **U8 depends only on U5/U6, never U10** — cost is a "no data yet" render slot (the edge points U10→U8,
  avoiding a U8↔U10 cycle).
- Consolidator = **type-tier-then-leverage**, one kind per node (terminal wins over gate).

**Requirements (honest facet scope):** U8 owns **R17** (derived-on-read cockpit) + **R18** (consolidator)
+ **R19** (report) + **R25** (projection) + **AE5** + **F3/F5/F6**. The realized-cost *population* is U10;
U8 only renders the slot.

**Checks run:** `ruff check .` ✓, `ruff format --check` ✓, `mypy plugins/ scripts/ tests/` ✓ (80 files),
`pytest` two U8 files ✓ 16 passed; full suite ✓ 1183 passed (1 local-only `.claude/`-dir guard deselected,
green in CI); validators ✓.

**Adversarial verification:** committed first (per the U4 lesson; every verify prompt forbade destructive
git + editing plugins/tests/docs), then ultracode workflow `verify-outcome-u8` — 5 refutation lenses
(consolidator, report-determinism, projection, acyclicity/dead-wiring, robustness) + a synthesis judge,
each running the modules standalone (+ a real git repo for the report). **The core guarantees HELD under
executed attack: R19 report determinism + overwrite-from-state, R25/R17 generated projection with no
operator-settable status + keystroke-only parent-close, and the U8↔U10 acyclicity (cost as a "no data
yet" slot, the edge pointing U10→U8).** One P1 + four P2 + two P3 folded:
- **P1 (sticky HALT broke healthy→empty)** — `_halted_subplots` returned any sid that EVER had a
  `phase=halt` dispatch record, so a halted-then-recovered (`done`) or halted-then-re-dispatched
  (`commit`) node was flagged `ambiguity` forever (and masked the real ship-gate). **Fix:** make it
  latest-record-wins (a later `commit` supersedes the `halt`) **and** guard the ambiguity branch on
  `state not in TERMINAL_STATES`. Regression: halt→done → empty; halt→commit(gated) → gate.
- **P2** — the report claimed "every non-gated leaf is auto-advancing" while the **whole frontier was
  frozen awaiting `/outcome approve`** (R20). **Fix:** the consolidator now emits a tier-1 **approval**
  attention item when the current revision is unapproved with a non-empty ready frontier — so a
  started-but-unapproved outcome is correctly NOT a healthy empty surface (and `/outcome attend` + the
  report + the projection all show it).
- **P2** — `progress.percent` read **100% while `complete==False`** (banker's rounding: 199/200→100).
  **Fix:** `display_percent` caps at 99 below completion, floors a non-zero at 1, 100 only when
  `done==total`; applied to report + projection.
- **P2** — the projection `frontier` re-listed **negative-terminal/HALTed nodes as ready** (a
  success-only `ready_frontier` let a dead leaf re-enter). **Fix:** derive the frontier from the same
  `states` map (`st=='ready'`) in the projection **and** `outcome.status()` (cross-surface).
- **P2** — a non-slug `subplot_id` (a `|`/space/backtick/newline) **corrupted the markdown table +
  Mermaid fence**. **Fix:** enforce a slug charset (`[A-Za-z0-9._-]+`) on `subplot_id` in
  `Node.validate` — fail-loud at source before any dispatch (R31), covering every downstream render +
  paths; plus strip newlines from the objective in the report H1.
- **P3** — `_cost_cell` showed "no data yet" for a non-empty cost dict lacking `tokens`/`wall_seconds`
  (and dropped a real `0`); now renders every present key sorted. **P3** — corrected a stale prune
  comment (U8's projection is artifact-only; the sub-issue close adapter is deferred).

**Refuted (no change):** report determinism + overwrite-from-state (byte-identical across re-render AND
across separate processes), the projection no-operator-writable-status + keystroke-only parent-close, the
U8↔U10 acyclicity, and (per the design carve-out) a merely-ready gated node is NOT a consolidator gate.

## U9 — Full backend menu, degradation policy, heartbeats

**Built:** `plugins/saga/scripts/outcome_dispatcher.py` (extended: full menu + degrade decision +
recommender) + `plugins/saga/scripts/outcome_liveness.py` (new: heartbeats + the `stalled` terminal) +
`plugins/saga/references/operator-choice.md` §8 + `tests/test_outcome_backends.py` (15) +
`tests/test_outcome_liveness.py` (8). Wiring in `outcome.py`: the degrade decision in `_reconcile_once`
(`available` / `attending`), a `liveness_processor`, `--autonomous` / `--host-capable` /
`--workflow-available` flags, `AdvanceResult.liveness` / `.degraded`, and the degrade receipt surfaced in
the report's Degradations section.

**What it ships:**
- **Full menu** (R6): `resolve_available()` — host-conditional, off-by-default for the host-dependent
  backends (fork/subagent/goal/cc-workflows-ultracode); always-available floor inline/team-execution/manual.
- **Presence-conditional degrade** (R23/AE1): `degrade_decision` — attending → HALT; guarantee-bearing →
  HALT; side-effected (destructive) → HALT; else autonomous+away → degrade one rung down the
  cc-workflows→team-execution→inline ladder + a visible `DegradeReceipt`; off-ladder → HALT.
- **Liveness** (R31): `harvest_liveness` reclaims a dispatched leaf breaching heartbeat/timeout as
  `stalled` (idempotent → pages once, cascades R22); `record_heartbeat` resets the deadline.
- **Recommender levers** (R7): `recommend_outcome_backend` (wide frontier → downgrade off cc-workflows) +
  `fork_is_cheap` (fork claimed cheap only when model+system+tools match within the cache TTL).

**Key decisions:** (full rationale → DECISIONS `#outcome-backend-degrade-stance`)
- The menu is host-conditional + OFF by default (the coordinator never claims a backend it can't verify).
- The degrade DECISION lives in the reconcile loop (it has the store + node + presence), not the
  dispatcher seam (a pure minter) — the str-returning `Dispatcher` contract U4–U8 rely on is unchanged.
- HALT vs degrade = presence × guarantee × side-effect, in that precedence; `destructive` is the
  side-effect proxy; presence is a per-advance signal (`--autonomous`).
- Liveness is timestamp-derived (dispatch `at` + heartbeat `at`), opt-in via the node budgets.

**Requirements (honest facet scope):** U9 owns **R3** (dispatch-not-execute, preserved) + **R5** (the
seam) + **R6** (full menu) + **R7** (recommender levers) + **R23** (degrade) + **R24-telemetry-CAPTURE**
(the executor-used + degrade/halt receipts; the rollup is U10) + **R31** (liveness). Plan deviation noted:
the frontier-budget lever lives in `outcome_dispatcher` (an outcome concern) not `lifecycle_state` (kept
saga-generic), and liveness is `outcome_liveness.py` not `lifecycle_state.py`.

**Checks run:** `ruff check .` ✓, `ruff format --check` ✓, `mypy plugins/ scripts/ tests/` ✓ (82 files),
`pytest` two U9 files ✓ 23 passed; full suite ✓ 1218 passed (1 local-only `.claude/`-dir guard deselected,
green in CI); validators ✓. One existing U4 test updated (`manual` is now an always-available backend, so
it dispatches rather than HALTs).

**Adversarial verification:** committed first (per the U4 lesson; verify prompts forbade destructive git
+ edits), then ultracode workflow `verify-outcome-u9` — 5 refutation lenses (degrade-decision, liveness,
loop-wiring/R3, recommender/menu, compat) + a synthesis judge, each running the modules standalone (+ a
real repo for advance). **The core HELD under re-executed attack: the degrade precedence + ladder (14
cases), `resolve_available` menu construction, the frontier-budget downgrade + fork-when-cheap recommender,
`is_guarantee_bearing`, R3 (the coordinator never executes), the never-HALT production dispatcher, and
per-store report determinism.** Two real P2 defects (both append-only-ledger discipline) folded:
- **P2 (liveness false-stall)** — `_is_stalled` used the heartbeat `at` directly (not floored at
  dispatch) and `_last_heartbeat` kept the write-order-last `at` (not the max). A **pre-dispatch
  heartbeat** (clock skew) or an **out-of-order heartbeat append** false-stalled a *live* leaf (a sticky
  terminal that cascades + pages). **Fix:** `last_activity = max(dispatched_at, last_beat)` + take the
  **max `at`** per sid (latest by timestamp, not by write order). Regressions: CASE A (heartbeat < dispatch)
  + CASE B (out-of-order appends).
- **P2 (non-idempotent halt/degrade records)** — a HALTed/degrade-then-crashed leaf never writes a commit
  (the dedup marker), so an attended leaf polling `advance` against an unavailable backend re-appended a
  `halt` record **every tick** (5 advances → 5 records, unbounded under normal operation), and a crash in
  the degrade→commit window double-listed the degradation. **Fix:** `_append_ledger_once` dedups on
  `(phase, key)` (the `import_bundle` pattern) for the halt + degrade records. Regressions: 5-advance →
  1 halt record; crash-window → 1 degrade record (still 1 dispatch — the commit dedup held throughout).

**Refuted (no change):** the degrade precedence/ladder (no degrade-up, no off-ladder target, no
slice off-by-one), the menu construction + recommender + fork-cheap gating, R3 + the never-HALT production
dispatcher + per-store report determinism, and (wontfix/by-design) `had_side_effect = destructive` errs
toward HALT (never a silent substitution) + `recommend_outcome_backend` is advisory only (the real
guarantees are enforced in `degrade_decision`/`_reconcile_once`, not the recommendation).

## U10 — Economics + optimize/retro consumers

**Built:** `plugins/saga/scripts/outcome_costs.py` (the producer + rollup) + the `cost_processor` wiring
in `outcome.py` + `skills/optimize/SKILL.md` (Outcome-economics baseline §) + `skills/retro/SKILL.md`
(§1.7 evidence pass) + `tests/test_outcome_economics.py` (11). Reuses `scripts/override_rate_reader.py`.

**What it ships:**
- **Producer** `record_cost(store, sid, executor/tokens/wall_seconds/operator_touches/retries/evidence)`
  — a leaf reports its own realized cost (R3: the coordinator never runs the leaf).
- **Consumer** `rollup(spec, store)` — per-outcome sums + `by_executor` + the **DAG-vs-one-thread**
  verdict (`wall_seconds_parallel` = critical path vs `wall_seconds_serial` = sum, `beat_one_thread`);
  empty → "no data yet"; missing leaves counted not zeroed; pruned-node cost → `sunk` (R33, the U7 defer).
- **Wiring**: a `cost_processor` in `advance` **materializes** the rollup into `spec.cost_rollup` (the
  producer → spec → U8-report edge — no U8→U10 dependency); `AdvanceResult.costs`.
- **Consumers**: `/optimize` cites the rollup as a portfolio baseline; `/retro` §1.7 reads it as evidence
  (both read-only, both with the "no data yet" contract).

**Key decisions:** (full rationale → DECISIONS `#outcome-economics-stance`)
- Cost is a **leaf-produced ledger fact**, the coordinator only aggregates+materializes (R3 intact).
- The edge is **U10 → `spec.cost_rollup` → U8**, never U8→U10 (the acyclicity rule; push the value into
  the shared canonical artifact the consumer already reads, no back-edge import).
- The thesis answer is **critical-path vs serial** — falsifiable (a pure chain honestly reports `False`).
- Honest "no data yet" + missing-count + sunk-cost (the U8 stance, kept).

**Requirements (honest facet scope):** U10 owns **R7** + **R24** (the rollup + the optimize/retro
portfolio consumer); it fills the U8 report's "no data yet" cost slot and the U7 pruned-node cost
reconcile. `override_rate_reader.py` (the R12 override signal) is reused, not modified.

**Checks run:** `ruff check .` ✓, `ruff format --check` ✓, `mypy plugins/ scripts/ tests/` ✓ (83 files),
`pytest tests/test_outcome_economics.py` ✓ 11 passed; full suite ✓ 1233 passed (1 local-only `.claude/`-dir
guard deselected, green in CI); validators ✓.

**Adversarial verification:** committed first (per the U4 lesson; verify prompts forbade destructive git
+ edits), then ultracode workflow `verify-outcome-u10` — 4 refutation lenses (rollup/critical-path,
honesty/sunk, latest-cost-ledger, acyclicity/wiring/R3) + a synthesis judge, each running the modules
standalone (+ a real repo for the report). **HELD under re-executed attack:** the acyclicity (the report
does NOT import `outcome_costs`; `outcome_costs` imports only `outcome_store` + lazy `outcome_spec`), the
`cost_processor` wiring + materialize-only-when-changed, R3 (the coordinator only aggregates, never runs a
leaf), determinism, and the no-data-yet / missing-counted / pruned→sunk honesty paths. One P1 + two P2 +
two P3 folded:
- **P1 (fabricated DAG win)** — a pure serial chain declared in **reverse-topo order** with fractional
  walls summed `serial` (declaration order) 1 ULP above `parallel` (topo order), so a bare `parallel <
  serial` flipped the headline R24 verdict to a fake win. **Fix:** `math.fsum` (order-independent) + a
  tolerance compare (`serial - parallel > 1e-9·max(|serial|,1)`). Regression: reverse-topo chain, fractional
  walls → `beat_one_thread False`.
- **P2 (per-field fabricated zeros)** — a leaf recording only its executor surfaced `tokens:0.0` /
  `retries:0.0` as hard facts (the `{}` guard was whole-rollup only). **Fix:** a numeric field is **emitted
  only when ≥1 leaf reported it** (omitted otherwise — no fabricated 0); the wall/serial/parallel/beat
  trio only when wall was reported. Regression: executor-only record omits the numeric fields.
- **P2 (mixed-timestamp lockout)** — once a sid had a timestamped record, a physically-later
  *untimestamped* report was silently dropped (stale cost). **Fix:** `_latest_costs` is write-order-last
  when EITHER record is untimestamped, max-by-`at` only when both are timestamped. Regression: later
  untimestamped supersedes earlier timestamped.
- **P3** — `record_cost` `float()`'d a bool/str `at` (True→1.0 epoch / `ValueError`); now validated
  (rejects a non-timestamp `at`). **P3** — the `/optimize` SKILL overclaimed `by_executor` as per-leaf
  cost; reworded to "backend mix / counts" + points per-leaf cost at `subplot_cost`.

**Refuted (no change):** acyclicity + wiring + R3 + determinism + the honesty paths (all re-checked
holding); the latest-cost SNAPSHOT-replace (not a field-merge — by design, matches the docstring); the
per-subplot report Cost column rendering `node.cost` (an authoring facet, not the realized telemetry).

## U11 — Release, docs, integration gate (THE FEATURE-FLIP — the OutcomeOrchestrator ships)

**Built:** the saga-feature-level flip + the all-34 composition gate. CHANGELOG `[Unreleased]` → `## 0.38.0`;
`plugins/saga/.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` → **0.38.0** (the release
triad now matches); the saga descriptions advertise the OutcomeOrchestrator (the `outcome-orchestration`
keyword replaces the redundant `sdlc`, within the 200-char `maxLength`); README + `docs/commands.md` →
**20 files / 19 routable**; the Command Matrix visual (`render_docs_visuals.py` +
`docs/assets/command-matrix.svg`) gains the `/outcome` coordinator card + the "19 routable" subtitle
(regenerated, golden test green); `tests/test_outcome_integration.py` (new); `tests/test_saga_plugin.py`
version pin → 0.38.0.

**What it ships:**
- **The feature flip** (R4 + all release surfaces): saga **0.38.0** advertises `/outcome` across
  plugin.json, marketplace.json, README, commands.md, and the command-matrix visual.
- **The integration gate**: `test_outcome_integration.py` drives the whole vertical slice through the
  **production** `advance` wiring on a real DAG + a stateful fake `gh` + a real git repo — start →
  approve (R20) → dispatch (R5) → GitHub-canonical harvest (a non-code leaf on a closed issue + a code
  leaf on a merged PR, R11) → auto-merge (R12) → cost rollup materialized (R24) → report (R19) +
  projection (R25) → `complete`. A second test affirms the thesis (a parallel fan-out `beat_one_thread`).

**Key decisions:** (full rationale → DECISIONS `#outcome-release-flip-stance`)
- The flip is a **version-triad bump + advertise-the-complete-surface + a compose-it-all gate**, NOT a
  retroactive drift sync (KTD14 kept each surface synced per-unit).
- The integration gate proves **composition** (the units run together), distinct from the per-unit
  requirement pins. It caught a fake-`gh` argv-mismatch during authoring — exactly the compose-bug class a
  unit test misses.
- Minor bump (0.37 → 0.38): additive, backward-compatible; bandit is `-ll || true` (informational) and the
  new scripts are clean at `-ll`.

**Requirements:** U11 closes **R4 + all release-facing surfaces** and asserts **all 34 (R1–R34) compose**.
The OutcomeOrchestrator is now **complete**: 11/11 units merged (U1 #261-era … U10 #273), saga 0.38.0.

**Checks run (the full U11 bar):** `pytest` ✓ **1239 passed** (incl. the 2 integration tests + the
release-triad + saga-plugin + docs-coverage golden); `ruff check` ✓, `ruff format --check` ✓, `mypy` ✓
(84 files), `validate_plugins` ✓, `marketplace/validator` ✓, `bandit -ll` on `outcome_*` ✓ (0 Medium/High).
(The one local-only `.claude/`-dir guard is deselected, green in CI.)

**Adversarial verification:** committed first (per the U4 lesson), then ultracode workflow
`verify-outcome-u11` — 3 lenses (integration-rigor, release-consistency, all-34-coverage) + a synthesis
judge — which returned **`ship_ready: False` and was RIGHT**. The version triad, validators, visuals, the
description/keywords within limits, and 1239 tests all HELD; one **P0** + a P1 + two P2 folded (all
re-verified by the judge):
- **P0 (R26/R27 persistence was a no-op → "all 34 ship" was false)** — `save_spec` wrote the working tree
  but nothing committed/pushed the spec to a branch, so cross-machine cold re-entry (F5) could not hold.
  **Fixed by IMPLEMENTING it** (not downgrading the claim): `outcome.commit_spec` commits + pushes the
  spec to the outcome's own branch (refuses on `main`/`master`, R26), via `/outcome commit [--push]` +
  `/outcome advance --persist`; a real-git test reads the committed blob back to prove a different-machine
  pull reconstructs the outcome.
- **P1 (the gate never exercised dispatch)** — `merge_processor`-then-`harvester` completed both leaves on
  tick 0 before dispatch ran, so the test passed even with a raising dispatcher. **Fixed:** the fake `gh`
  now resolves a leaf's issue/PR only after a settled dispatch record, and the test asserts
  `all_dispatched == {design, build}` — dispatch is load-bearing.
- **P2 (auto-merge ignored the DAG frontier)** — a clean PR for a leaf with an incomplete (especially
  non-code) upstream could squash out of order. **Fixed:** `process_merge_queue` gates on
  `all(dep in success)` + a regression.
- **P2 (stale doc counts)** — `docs/README.md` + `docs/boundaries.md` still said 18/17 → moved to 20/19.

**Refuted (no change):** the release version triad (0.38.0 across plugin.json / marketplace.json /
CHANGELOG / the test pin), the description length + keyword cap, the command-matrix golden (render-to-temp
byte-identical with the `/outcome` card), the validators, and R8/R30/R13/R22/R34 genuinely covered. After
the fold the gate's blocking finding is resolved — **all 34 genuinely ship**.

---

## OUTCOME: the OutcomeOrchestrator shipped (11/11 units, R1–R34)

Built across 11 per-unit PRs, each landed independently-releasable with its release surfaces synced
(KTD14) and gated by an ultracode adversarial-verify pass (commit-before-verify per the U4 clobber
lesson). Every verify found real defects and folded them with regressions — the recurring families:
**"the system that owns the resource is the guard, degrade-safe"** (U6 GitHub `--match-head-commit`, U7
git-is-the-liveness-oracle), **the append-only-ledger discipline** (U8 latest-not-ever, U9 max-by-timestamp
+ append-once, U10 latest-cost), **acyclicity through the shared artifact** (U8 no-U10-dep, U10
producer→spec→U8), and **all-fake-tests-miss-the-real-adapter** (U7 path canonicalization, U11 fake-`gh`
argv). saga **0.38.0** ships `/outcome` — the coordinator that drives a whole outcome as a durable DAG of
leaf sagas.
