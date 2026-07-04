# Work Session — Gate-Divergence Telemetry (#399)

- **Plan:** `docs/plans/2026-07-04-gate-divergence-telemetry-plan.md`
- **Doc review:** `docs/reviews/2026-07-04-gate-divergence-telemetry-plan-review.md` (not blocked,
  zero findings after 3 in-place fixes)
- **Saga:** `issue-399`
- **Branch:** `docs/pf-gate-divergence-telemetry-399`
- **Destination:** merge
- **Backend:** inline

## Units completed

- **U1** — Added `gate_divergence: ListOrAbsent = ABSENT` to the `Saga` dataclass
  (`plugins/saga/scripts/saga.py:217`), registered in `FRONTMATTER_FIELDS`/`_LIST_FIELDS`, plus
  `--gate-divergence` (repeatable CLI arg), `encode_gate_divergence_entry()`, and
  `parse_gate_divergence_entry()` (base64-wrapped JSON per KTD1). Verified: 7/7 tests in
  `tests/test_gate_divergence.py` pass, including a regression test for the exact
  pipe-in-answer corruption mode doc-review flagged.
- **U2** — `plugins/saga/references/gate-divergence-instrumentation.md`: the two-timestamp +
  base64-encode convention every instrumented skill points at.
- **U3** — `plugins/saga/scripts/gate_divergence_reader.py`: per-gate rubber-stamp rate,
  zero-data contract, read-only. Deviated from the plan's literal wording (which anticipated
  mirroring `override_rate_reader.py`'s lightweight line-based frontmatter parser) — during
  execution, verified that `gate_divergence` is a multi-line YAML list field with base64+JSON
  entries that the simple line parser cannot decode correctly, so the reader imports
  `saga.py`'s own `parse_envelope`/`parse_gate_divergence_entry` instead (same CLI surface,
  same injectable-root pattern, more correct parsing). 7/7 tests pass, including a CLI smoke
  test against the committed fixture.
- **U4** — Instrumented all 5 cited `AskUserQuestion` gate sites. `founder-review/SKILL.md`
  confirmed to fire 2 distinct gates under one citation (mode-selection `:133`,
  per-expansion opt-in `:144`), each given its own `gate_id` per the plan's U4 note. Verified:
  `grep -rln gate-divergence-instrumentation plugins/saga/skills/{brainstorm,founder-review,investigate,loop,outcome}/SKILL.md`
  returns 5 files.
- **U5** — `/retro` Phase 1.6a wired, running `gate_divergence_reader.py` read-only alongside
  the existing R12 reader. Verified: `grep -n gate_divergence_reader plugins/saga/skills/retro/SKILL.md`
  matches.
- **U6** — Tests, fixtures, release surfaces. Two corrections found during execution (both
  citation/naming drift, not plan-blocking): the real version-parity test is
  `tests/test_release_triad.py` (not the issue's suggested `test_marketplace_drift.py`, which
  doesn't exist), and the real override-rate regression suite is `tests/test_override_rate.py`
  (not `test_override_rate_reader.py`). Both run clean. Bumped `plugin.json`/`marketplace.json`
  `0.51.0` -> `0.52.0`, added the `CHANGELOG.md` entry, fixed the hardcoded version literal at
  `tests/test_saga_plugin.py:48`.

## Closeout

- Ticked Phase 0 checklist row 2 in `docs/plans/2026-07-04-plugin-fleet-execution-order.md`.
- Release surfaces: `plugin.json` (0.52.0), `.claude-plugin/marketplace.json` (synced),
  `plugins/saga/CHANGELOG.md` (entry added) — all in this commit.
- Board hygiene: issue #399 was already board-onboarded (carries `hermes-task`, unlike #461's
  anomaly) — advanced Status Idea -> Active at plan start via `sdlc_manager.py flow set-field`.
- Test gate: `requires_hard_test_gate` applies (behavior change — new field, new script, new
  skill instructions). Full suite run: 1887 passed, `ruff format --check` clean, `ruff check`
  clean, `mypy plugins/ scripts/ tests/ --ignore-missing-imports` clean (121 source files, no
  issues).
- A real gitignore trap surfaced and was fixed: `.gitignore:55` excludes `.claude/` globally,
  but the committed fixture directory (`tests/fixtures/gate_divergence_sagas/`) necessarily
  nests envelope files under `.claude/saga/sagas/` (the reader's hardcoded scan path, matching
  `override_rate_reader.py`'s own convention) — `git add` would have silently dropped them.
  Force-added with `git add -f`, documented here so a future `git clean` pass doesn't
  rediscover this as a mystery.

## Follow-on (not this issue's scope)

- The plan deferred exhaustive per-file gate enumeration for `brainstorm`, `investigate`,
  `loop`, and `outcome` beyond the one concrete site instrumented in each (only
  `founder-review` was checked closely enough during doc-review/execution to confirm it fires
  2 distinct gates). A future pass through those 4 files for additional un-instrumented gate
  sites is worth a `QUEUED.md` seed, not fixed here.

## Next step

Run `/code-review` programmatically against this branch, then open the PR (or merge directly,
per destination `merge`) under explicit confirmation.
