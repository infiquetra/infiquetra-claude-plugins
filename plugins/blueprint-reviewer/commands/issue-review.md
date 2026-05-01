---
name: issue-review
description: Review a GitHub issue using the issue-phase rubric library
---

Run a multi-reviewer review of a GitHub issue. Findings get posted
as a single consolidated comment on the issue.

## Usage

```
/issue-review <issue> [--reviewers <slug,slug,...>] [--cores-only] [--dry-run] [--no-post]
```

## Arguments

- `issue` — GitHub issue reference. Accepted shapes:
  - `owner/repo#42`
  - Full GitHub URL
  - Issue number (in current repo context)
- `--reviewers <slug,slug,...>` — Run only named reviewers.
- `--cores-only` — Skip conditional extras.
- `--dry-run` — List reviewers WITHOUT scoring or posting.
- `--no-post` — Score + format the comment, but don't post it
  (useful for previewing).

## Examples

```
/issue-review infiquetra/campps-mvp#42
/issue-review infiquetra/mimir#418 --cores-only
/issue-review #15 --reviewers spec_fidelity,acceptance_criteria_clarity
/issue-review owner/repo#9 --dry-run
```

## What This Does

1. Fetches the issue (`gh issue view`).
2. Finds + reads the parent spec (if cited in the issue body) so
   `spec_fidelity` can check actual descent.
3. Reads existing comments so prior reviews don't get repeated.
4. Runs the always-applicability **issue-phase cores**:
   `devils_advocate_issue`, `spec_fidelity`,
   `acceptance_criteria_clarity`.
5. Picks 0–3 conditional extras based on issue content.
6. Produces a summary table + per-reviewer findings.
7. Posts a single consolidated comment to the issue.
8. Surfaces action items + suggests next step (move to Ready, or
   address REVISE items).

## Script Command

The skill invokes:

```bash
python3 ~/.claude/plugins/cache/infiquetra-plugins/blueprint-reviewer/0.1.0/scripts/lifecycle_review.py \
  rubrics list-cores --phase issue
python3 ~/.claude/plugins/cache/infiquetra-plugins/blueprint-reviewer/0.1.0/scripts/lifecycle_review.py \
  rubrics read --phase issue --slug <slug>
gh issue view <owner>/<repo>#<num> --json title,body,labels,state,assignees
gh issue view <owner>/<repo>#<num> --comments
gh issue comment <owner>/<repo>#<num> --body-file /tmp/review-comment.md
```

## Instructions

When the user invokes `/issue-review`:

1. Parse the issue reference.
2. Use the `issue-review` skill to drive the procedure.
3. **Critical:** find and read the parent spec — if not named in the
   issue, that's already a `spec_fidelity` finding.
4. **Always post a single consolidated comment** — don't post one
   comment per reviewer. The summary table + details should be
   one well-formatted markdown blob.
5. End the agent's response with the comment URL + action items.

This is **advisory review**. Specifically:

- **Do NOT** move the issue to Ready.
- **Do NOT** apply suggested AC changes.
- **Do NOT** add labels.
- **Do NOT** edit the issue body.

Findings are posted; the human decides whether to address them and
when to promote.

## Difference from automated PR-driven review

This command is the **manual** path. The **automated** path (Phase C,
future) will trigger when an issue moves to **Backlog** on the
Olympus project board, run the same rubrics, and post the same
comment shape. The two paths share the rubric library so findings
are consistent between them.
