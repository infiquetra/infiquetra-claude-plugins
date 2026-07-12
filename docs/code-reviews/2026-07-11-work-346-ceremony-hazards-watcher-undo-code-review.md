# Code review — work/346-ceremony-hazards-watcher-undo

**Verdict: CLEAN — not blocked.** 0 unresolved P0/P1. All actionable findings fixed on-branch in
`e29b707` and re-verified adversarially (8/8 fix claims upheld, zero refutations, regression sweep
clean); the review is fresh at that SHA (any later commits are this artifact and session docs — no
code moved).

- **Target:** branch diff `478f3e7..e29b707` (merge base = origin/main `478f3e7`, verified fresh)
- **Reviewed SHA:** `e29b707` (initial 4-lens pass at `653f610`; staleness re-review of
  `653f610..e29b707` passed — every fix claim falsification-tested, all upheld)
- **Mode:** programmatic (called by `/work` as the pre-PR gate); envelope persisted here by `/work`
- **Linked issue:** infiquetra/infiquetra-claude-plugins#346 · **PR:** #562 (draft)
- **Plan:** `docs/plans/2026-07-11-issue-346-ceremony-hazards-watcher-undo-plan.md`
- **Work-session:** `docs/work-sessions/2026-07-11-issue-346-ceremony-hazards-watcher-undo.md`

## Scope check: CLEAN

Intent (issue #346 / plan): one safety layer over `ship_ceremony.py` — hazard preflight
(`ceremony_hazards.py`), deterministic merge expectation (`merge_watcher.py`), rollback manifest +
forward-only gated `ship --undo` (`ship_undo.py`), wired into `run()` behind the #526 gate; docs +
release surfaces (0.77.0) in the same PR. Delivered: exactly the 15 plan-named files plus
plan/spec/review orchestration artifacts. The maintainability lens confirmed release-surface parity
(plugin.json == marketplace == CHANGELOG == drift-guard pin, all 0.77.0). No drift.

## Findings (stable numbering; lenses: correctness, security, testing, maintainability)

| # | Sev | Conf | File | Finding | Status |
|---|---|---|---|---|---|
| 1 | P1 | 90 | `ship_undo.py:146` | `_sha_reachable()` was local-only (`git cat-file -e`) — false `SHA_UNREACHABLE` refusal in the merge-landed-but-not-pulled window (empirically reproduced) | **fixed** `e29b707` — best-effort `git fetch origin` then re-probe; integration oracle `test_sha_reachable_fetches_missing_origin_object`; LEARNINGS `{#local-reachability-blind-to-origin-346}` |
| 2 | P2 | 85 | `merge_watcher.py:144`, `ship_undo.py:164` | Unvalidated `saga_id` becomes a path component — traversal via `sidecar_path()`/`manifest_path()` | **fixed** `e29b707` — `_validate_saga_id` (fullmatch `[A-Za-z0-9][A-Za-z0-9._-]*`) inline in both derivations; re-reviewer's traversal battery (`..`, `a/../b`, `/abs`, `-x`, `a\b`, …) all refused |
| 3 | P2 | 80 | `ship_undo.py:332` et al. | Manifest-sourced branch/SHA values reach git argv unhardened (`git checkout <branch>` etc. — an option-like value parses as a flag) | **fixed** `e29b707` — `_require_option_safe` leading-dash refusal on branch/head_sha/merge_sha + `--` separators (each placement verified against real git); `ExplodingRunner` proves refusal precedes any shell-out |
| 4 | P2 | 80 | `ship_undo.py:255`, `merge_watcher.py:188/203` | Sidecar-sourced `pr_number` reaches `gh pr close`/`gh pr view` argv unvalidated | **fixed** `e29b707` — `[0-9]+` fullmatch in both modules and in `ceremony_hazards._probe_merge_not_landed` (fail-loud, never "no hazard") |
| 5 | P2 | 85 | `merge_watcher.py` (CLI) | CLI boundary zero-covered: module 74% vs 80% bar; `watch()`-level `pr_not_open`/`check_missing`/`review_regressed` untested | **fixed** `e29b707` — CLI record/validate/watch round-trip tests + all five divergence kinds now exercised at `watch()` level; coverage 74% → **97%** |
| 6 | P2 | 75 | `ship_undo.py:91` | `SHAUnreachableError` carried no remedy, breaking the KTD8/KTD3 remedy-line contract its sibling refusal errors honor | **fixed** `e29b707` — `.remedy` folded into `str(err)`, names post-fetch recovery options |
| 7 | P3 | 80 | `ship_undo.py:174`, `merge_watcher.py:151`, `_saga_cli` | `json.JSONDecodeError` escaped the module error types at CLI boundaries (raw traceback on corrupt sidecar/manifest) | **fixed** `e29b707` — wrapped into named `ShipUndoError`/`MergeWatcherError` refusals; the existing `ship_ceremony.py:830` catch tuple now covers them for free |
| 8 | P3 | 80 | `ship_undo.py:182`, `merge_watcher.py:159` | Non-atomic sidecar writes (truncation window) | **fixed** `e29b707` — tmp + `os.replace`, mirroring `saga.py:_atomic_write`; no-tmp-left oracles |
| 9 | P3 | 75 | `merge_watcher.py:168-177` | Legacy StatusContext (`context`/`state`) check-shape fallback untested | **fixed** `e29b707` — `test_normalize_handles_legacy_status_context_shape` |
| 10 | P3 | 75 | `ship_undo.py:294` | `merge_sha` TOCTOU (reachability probe vs revert; could verify descendant-of-main) | **report-only** — single-operator window, revert itself fails loud on a bad target |
| 11 | P3 | 75 | `ceremony_hazards.py` | Hazard-probe TOCTOU (probe-then-dispatch) | **report-only** — by design; the probe is a preflight, not a lock |
| 12 | P3 | 75 | `saga.py:953` | saga_id sanitization root cause lives upstream in saga.py | **report-only** — pre-existing, separate cleanup issue |
| 13 | P3 | 75 | repo-wide | `bandit -r plugins/` baseline has never been green (identical 656L/3M/2H at merge base) | **report-only** — pre-existing; honest gate is per-file delta (0 on all touched scripts) |

Suppressed: 1 (maintainability P3 at confidence 60 — `pre_merge_main_sha` written but never
consumed; below the 75 anchor. A docstring note marking it audit-only was folded into `e29b707`
anyway, at zero risk).

Residual from the re-review (advisory, not a refutation): `ceremony_hazards.py:156` passes the
saga-sourced branch to `gh pr list --base <branch>` without a leading-dash guard — a flag value on
a read-only command, not manifest-sourced, untouched by the fix round; exploitability not
demonstrable.

## Validation method

Four always-on lenses (correctness, security, testing, maintainability) ran as
`saga:readonly-verifier` agents in isolated worktrees, each fetching and checking out `653f610`
explicitly and reporting `examined_sha` (all four matched). The fix round was then
falsification-tested by a fifth adversarial pass at `e29b707`: each fix claim attacked directly
(traversal battery, real-git `--` placement checks in a scratch repo, offline-fetch degradation,
coverage re-measurement), verdict 8/8 uphold with an empty refutation list.

## Coverage / residual risk

- Full suite at `e29b707`: 3197 passed / 0 failed / 1 skipped (+32 tests from the fix round).
  Module coverage: `merge_watcher.py` 97%, `ship_undo.py` 95%, `ceremony_hazards.py` 94%. ruff
  check + `format --check`, mypy (CI scope), bandit (touched files 0→0), R5 grep guard all clean.
- Residual: findings #10-#13 stand as documented advisories; the `gh pr list --base` guard and the
  saga.py root-cause cleanup are candidates for a small follow-up issue, not #346 blockers.
- Panel context: the build carried refute-3 verifier panels on U3 and U4 (both unanimous uphold);
  completeness manifests persisted for U1-U6.

Review complete
