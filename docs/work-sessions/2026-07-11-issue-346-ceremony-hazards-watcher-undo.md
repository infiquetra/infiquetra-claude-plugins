# Work session — issue #346: ceremony hazards, merge-watcher, ship --undo

- **Issue:** infiquetra/infiquetra-claude-plugins#346
- **Plan:** `docs/plans/2026-07-11-issue-346-ceremony-hazards-watcher-undo-plan.md`
  (doc-review READY: `docs/reviews/2026-07-11-issue-346-ceremony-hazards-watcher-undo-plan-review.md`)
- **Branch / PR:** `work/346-ceremony-hazards-watcher-undo`, draft PR #562 (ceremony front-loaded)
- **Backend:** cc-workflows-ultracode (operator choice), run `wf_8d9869d8-103` — 12/12 agents done,
  0 errors, ~1.045M subagent tokens; spend 110 confirmed as emitted
- **Commits:** `2a5554a` (plan/spec/review/journal), `653f610` (implementation, 15 files),
  `e29b707` (code-review fix round, 8 files)

## What was built (by U-ID)

- **U1** (`ceremony_hazards.py` + tests, sonnet/medium): `Hazard` registry + `detect()` preflight —
  `stacked_pr` (acknowledgeable) and `merge_not_landed` (hard refusal, KTD3); non-gated transitions
  probe nothing; probe failure raises, never reads as "clean".
- **U2** (`merge_watcher.py` + tests, sonnet/medium): `record`/`validate`/`watch` over the
  `merge_expectation.json` sidecar (KTD1); five named divergence kinds; `record --force` the only
  re-baseline (KTD7); missing sidecar refuses with a remedy (KTD8); no sleeping in library code.
- **U3** (`ship_undo.py` + tests, sonnet/high + refute-3 panel): rollback manifest append/read;
  `undo()` newest→oldest, forward-only (KTD4 — revert commit, branch resurrection, never
  force-push/reset); `always_operator`-reversing plans gated on `--operator-confirmed undo` (KTD5);
  resumable via per-entry `undone` marks.
- **U4** (`ship_ceremony.py` wiring + tests, sonnet/high + refute-3 panel): preflight after the
  #526 gate, before dispatch/save (KTD2); `--acknowledge-hazard` choices from the registry;
  `merge_watcher.record` at PR-open/start, `validate` at merge; manifest append per transition;
  `run --undo` forks before the forward gate (KTD6); `_do_merge` captures pre/post ls-remote SHAs.
- **U5/U6** (haiku/low): `pr-continuation-loop.md` + SKILL.md watcher/hazard/undo contract;
  0.76.0 → **0.77.0** across plugin.json / marketplace.json / CHANGELOG / drift-guard pin;
  LEARNINGS `{#auto-merge-delete-branch-reorder}`.

Both refute-3 panels returned unanimous uphold. Completeness manifests persisted for U1-U6
(`manifest_store.py record-completeness`, exit 0). One post-harvest orchestrator fix: U1's
docstrings described the retired flags with literal tokens, tripping the R5 keep-clean grep —
reworded in place before commit.

## Checks run (merge base fresh: origin/main == 478f3e7)

- `uv run pytest -q` — 3197 passed, 0 failed, 1 skipped (3165 at `653f610`, +32 fix-round tests)
- `uv run ruff check .` + `ruff format --check .` — both clean
- `uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` — exit 0
- `uv run bandit` on the four touched scripts — 0 findings (repo-wide baseline pre-existing,
  identical at merge base)
- R5 guard: `grep -rE -- '--auto|--delete-branch' plugins/saga/` (minus `--autonomous`) — empty

## Code-review gate (programmatic)

4-lens pass at `653f610`: 13 findings + 1 suppressed, 1 P1 / 5 P2 / 7 P3 — all 9 actionable fixed
in `e29b707` (fetch-before-`SHA_UNREACHABLE`, saga_id path guards, option-safe argv + `--`
separators, PR-number validation, merge_watcher CLI coverage 74%→97%, remedy line, named JSON
refusals, atomic writes, legacy check-shape test). Staleness re-review at `e29b707`: adversarial
falsification of all 8 fix claims — 8/8 upheld, zero refutations, regression sweep clean. Artifact:
`docs/code-reviews/2026-07-11-work-346-ceremony-hazards-watcher-undo-code-review.md`.

## Process note

`run` was invoked before `start`, so the `commit` transition fired first and `start` (front-loaded
mode only) refused; the draft PR was created manually to the identical end state (`gh pr create
--draft` + `saga.py save --pr-refs "#562"`). Invariants hold — the later `open_pr` transition flips
the existing draft ready.

## Next step

Flip draft PR #562 ready + request review under operator confirmation (destination: merge).
