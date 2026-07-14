# Mission Control assign-to-Mimir plan

Issue: `infiquetra/infiquetra-claude-plugins#557`

## Goal

Add one fail-closed, idempotent Mission Control command that assigns an open issue in a live-covered repository to Team Mimir by applying the repository's existing `intake:mimir` trigger.

## Implementation

1. Add `flow assign-mimir --repo REPO --number N` to `sdlc_manager.py`.
2. Before mutation, read Team Mimir's `deploy/repository_coverage.yml` from GitHub `main`, require an active exact repository entry, read the target issue, verify the current GitHub principal has triage-or-higher authority, and verify the trigger label already exists.
3. Apply the label only when absent, then read back the issue. Report the issue URL, `applied` or `already-triggered`, live coverage route, expected Mimir route, and Objective field values from any project cards.
4. Add focused tests for covered, uncovered, already-triggered, unauthorized, missing-label, closed-issue, malformed coverage, mutation failure, readback failure, and CLI dispatch.
5. Update both operator skills, release metadata, marketplace mirror, and the engineering journal.

## Validation and delivery

- Run the issue's focused and repository quality commands.
- Review the merge-base diff and record the code-review result.
- Open, monitor, and merge the PR.
- Refresh and update the installed Mission Control plugin, verify version/readback, and run one live negative proof plus a reversible covered-repository canary.

## Stop conditions

Any failed coverage, issue, authority, label, mutation, or readback check is an explicit error. No alternate credentials, label creation, repository admission, comments, or closed-issue mutation are allowed.
