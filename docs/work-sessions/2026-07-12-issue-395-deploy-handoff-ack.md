# Work Session — Issue #395: positive handoff protocol at the saga -> deploy edge (2026-07-12)

One-line summary: executed the full plan via the approved `cc-workflows-ultracode` workflow
(`wf_6728d66b-307`, 11 agents, 0 errors), fixed all 8 code-review findings, survived a
three-round falsification loop that twice refuted the sweep fix (OSError abort, then a FIFO
hang), and reached PR-ready on PR #564 with every gate green.

## What was built (by U-ID)

- **U1** — `plugins/saga/scripts/deploy_handoff.py`: handoff-ack sidecar
  (`.claude/saga/sagas/<id>/deploy_handoff.json`) — `offer` (CSPRNG token, supersede-on-reoffer),
  `accept` (write-once, named errors), `authorize_promotion` (gate blocks; auto = nonprod only;
  staging/production always confirm), CLI verbs; thin `build_deploy_handoff_envelope()` delegator
  in `handoff_envelope.py` with the existing envelope byte-unchanged (R1/R3, KTD1/2/4/5).
- **U2** — `--deploy-autonomy {gate,auto}` on `saga.py save` (carry-forward-on-omit), saga-spec
  field row, `/plan` Phase 5.1 follow-up question, `offer` sourcing payload + pr_refs from
  `state.json["sagas"][saga_id]` — absent always reads `gate` (R2/R5, KTD3).
- **U3** — read-only `reconcile` verb, per-saga + `--all` sweep; offer-without-ack derives
  `handed-off-unacknowledged` (dropped baton, F2); exit 0 clean/no-handoff, 1 otherwise (R4, KTD6).
- **U4** — boundary docs both sides: handoff SKILL "Deploy edge", deploy-state SKILL "Accepting a
  saga handoff", deploy.md acceptance step; `/work` SKILL gained exactly 3 routing lines with the
  Hard boundary section untouched (R6/R7, AC7).
- **U5** — release surfaces: saga 0.78.0 → 0.79.0, deploy 0.1.4 → 0.2.0, marketplace both entries,
  both CHANGELOGs, both drift pins.

## Checks run

- Full suite at final SHA `99f3611`: **3318 passed / 0 failed / 1 skipped** (+57 in the new
  `tests/test_handoff_envelope.py`). All five issue AC `-k` selectors collect and pass; the
  testing lens proved them **non-vacuous via 7 code mutations**. AC6 grep 8 matches; AC7 verified.
- ruff check + format clean; mypy CI scope 0 errors; bandit delta clean (only house-accepted Low
  subprocess notes; the High `shell=True` hit is pre-existing in `agy_delegate.py`, untouched).
- Workflow refute-3 panels on U1/U2: 0 refuted across 6 verifiers; completeness manifests 5/5.
- 4-lens review + 3-round falsification: envelope at
  `docs/code-reviews/2026-07-12-work-395-deploy-handoff-ack-code-review.md`.

## Commits (branch `work/395-deploy-handoff-ack`, PR #564)

- `6a9da20` docs(plan): plan, spec, workflow, doc-review, KTD record
- `da33fbd` feat(saga,deploy): the full handoff-ack layer (17 files, +1280/−12)
- `5f746dd` fix: review round — sweep degrade, CLI e2e coverage, doc truthfulness
- `fc5cf50` fix: sweep degrades OSError sidecars (falsification round 1)
- `99f3611` fix: `_read_sidecar` refuses non-regular files pre-open — FIFO hang, dangling
  symlink, single-saga traceback (falsification round 2)

## Process notes

- The falsification loop refuted the same fix **twice**, each round with a strictly nastier
  vector: first the OSError abort (directory/chmod-000), then the FIFO **hang** — where nothing is
  raised at all, so exception-based degrade is structurally incapable of helping. The final fix
  moved the defense from the except clause to a pre-open `S_ISREG` check at the read root.
- Round 3 explicitly verified the legitimate case (symlink to a valid regular file) still works —
  an over-blocking "fix" would have been its own regression.
- The ceremony `start` for this PR ran on 0.78.0 code and registered both the branch and draft PR
  in the opened-resources manifest — the #347 empty-receipt gap confirmed closed for
  born-0.78.0 ceremonies.

## Next step

Flip PR #564 ready + request review (`open_pr` / `request_review` transitions), then the round-N
loop: merge under explicit operator confirmation, board moves, outcome `link-pr` + `advance` for
sub-395 — which completes the ship-ceremony-hardening outcome (4/4).
