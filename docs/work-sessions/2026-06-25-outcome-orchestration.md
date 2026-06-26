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

**Next step:** U3 — thin `/outcome` command + local reconcile skeleton.
