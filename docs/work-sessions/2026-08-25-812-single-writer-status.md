# Work session — #812 U7 Stage/Status corrections through mission-control

**Date:** 2026-08-25
**Issue:** infiquetra/infiquetra-claude-plugins#812
**Plan:** `docs/plans/2026-08-25-improve-claude-plugins-run-plan.md` unit U7
**Branch:** `orch/orch-2026-08-25-814-u-812`
**Backend:** inline (plan frontmatter)
**Engine:** none

## What was built (U7)

Guard-and-tighten, Status-only against the live board schema (S3-repaired plan). No
`set-field-stage` op-kind. No generic correction intake.

1. **Inventory (step 1).** Live field list 2026-08-25:
   - Operations (#3), Asgard (#2), CAMPPS (#4): Title, Assignees, Status, Labels,
     Linked pull requests, Milestone, Repository, Reviewers, Parent issue,
     Sub-issues progress, Created, Updated, Closed, Objective, Priority.
   - Status present on all three. Stage present on none.
   - Operations Status options: Idea, Shaping, Ready, Active, Verify, Done.
   - Zero saga GraphQL `updateProjectV2ItemFieldValue` (or sibling) mutations.
   - The only saga `--field` argv is `default_board_writer` in
     `plugins/saga/scripts/board_progression.py`.
2. **Submission seam.** `set-field-status` now:
   - defaults `payload["field"]` to `Status`;
   - GATEs any other field except Stage-by-name (`authorize_correction_field`);
   - keys retries as `{op}:{repo}#{n}:{field}:{target_state}`;
   - shells out to `flow set-field --field <name> --correction`.
   Other op-kinds (close, reopen, comment, labels) are untouched.
3. **Mission-control.** Existing `flow set-field` gains `--correction`. Operator writes
   without the flag still set Initiative/Objective. No new operation.
4. **Static guard.** `tests/test_saga_single_writer_guard.py` fails closed on a seeded
   direct-write fixture and is clean on the real saga tree.

## Key decisions

- Status-only live field; Stage allowed by name only. See
  `docs/engineering-journal/DECISIONS.md` `{#812-correction-field-named-identity}`.
- Unattended: plan `backend: inline`; engine none; no board writes on the run cards
  (R7); no push/PR (`merge: false` — controller lands this branch).

## Files modified

- `plugins/saga/scripts/reversibility_certificate.py`
- `plugins/saga/scripts/board_progression.py`
- `plugins/saga/scripts/reconcile_controller.py`
- `plugins/mission-control/scripts/sdlc_manager.py`
- `tests/test_saga_single_writer_guard.py` (new)
- `tests/test_reversibility_certificate.py`
- `tests/test_board_progression.py`
- `tests/test_outcome_board_sync.py`
- `plugins/mission-control/tests/test_flow_subcommands.py`
- release surfaces: saga 0.139.7→0.139.8, mission-control 2.12.2→2.12.3
- `docs/engineering-journal/LEARNINGS.md`, `DECISIONS.md`

## Checks run

- `uv run pytest tests/test_saga_single_writer_guard.py -v` — 5 passed
- `uv run pytest plugins/mission-control/tests/ -k "set_field or correction" -v` — 12 passed
- `uv run pytest plugins/mission-control/tests/ -k "certificate" -v` — 1 passed
- Live field-options receipt 2026-08-25: Operations/Asgard/CAMPPS have Status, none have Stage
- Live Status write on a scratch issue: **not executed**. This session's auto-mode
  blocked creating a GitHub issue and mutating the project board. The write path is
  proven by `test_correction_set_field_round_trips_field_in_identity` (MC GraphQL
  mutation with field identity) and `test_default_writer_emits_field_and_correction_flag`
  (saga argv → `flow set-field --correction`). Replay for the controller:

  ```bash
  python3 plugins/saga/scripts/board_progression.py write \
    --op set-field-status --repo infiquetra/infiquetra-claude-plugins \
    --number <scratch> --target-state Done --project operations
  ```

## Next step

Commit on this branch. Do not push or open a PR — the orchestrating session lands it.
