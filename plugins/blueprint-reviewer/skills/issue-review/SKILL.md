---
name: issue-review
description: |
  Review a GitHub issue using the issue-phase rubric library. Runs core
  reviewers (devils_advocate_issue, spec_fidelity, acceptance_criteria_clarity)
  and LLM-picked conditional extras. Findings posted as a single issue
  comment with summary table + per-reviewer details.
when_to_use: |
  Use this skill when the user wants to:

  Direct invocation:
  - "review issue infiquetra/campps-mvp#42"
  - "review this issue: <github URL>"
  - "/issue-review infiquetra/mimir#418"

  Pre-Ready / pre-card-pickup:
  - "before I move this to Ready, review it"
  - "is this issue agent-ready?"
  - "are the ACs tight enough?"

  Targeted reviewer:
  - "is this issue right-sized?"
  - "does this issue have enough technical context?"
  - "does this descend from spec X?"

  Surveying:
  - "what reviewers fire on the issue phase?"
---

# Issue Review

Run the issue-phase reviewer panel against a GitHub issue, producing
scored findings and posting them as a single issue comment with summary.

## Script Location

```
~/.claude/plugins/cache/infiquetra-plugins/blueprint-reviewer/0.1.0/scripts/lifecycle_review.py
```

(During development, also at:
`~/workspace/infiquetra/infiquetra-claude-plugins/plugins/blueprint-reviewer/scripts/lifecycle_review.py`)

## Procedure

### 1. Identify the issue

If the user pointed at a `<owner>/<repo>#<num>` or a GitHub issue URL,
parse it. Otherwise ask: "which issue should I review?"

Fetch the issue body + metadata:

```bash
gh issue view <owner>/<repo>#<num> --json title,body,labels,state,assignees,projectItems
```

If `gh` returns "issue is closed," ask the user whether to proceed
(closed issues are usually NOT worth reviewing unless reopening
them is on the table).

### 2. Find and read the parent spec

The issue should descend from a spec. Look for:

- A `Spec:` link in the issue body (typical convention)
- A reference to a `*-blueprint` repo's `specs/<area>/<spec>.md`
- A milestone or label that maps to a known spec

If the spec is named, READ IT — `spec_fidelity` checks descent. If
no spec is named, that's already a `spec_fidelity` finding.

For repos in the working set (e.g. `infiquetra/campps-mvp`), the
parent spec typically lives in the corresponding blueprint repo
(e.g. `infiquetra/campps-context-library/specs/...`).

### 3. Read existing comments

Before reviewing, read any prior comments on the issue:

```bash
gh issue view <owner>/<repo>#<num> --comments
```

If a previous review-comment exists (the comment will have a summary
table), don't repeat findings already raised — call out which
findings persist and which are new.

### 4. Determine which reviewers run

**Always:** all issue-phase cores:

```bash
python3 <SCRIPT> rubrics list-cores --phase issue
```

Today returns: `devils_advocate_issue`, `spec_fidelity`,
`acceptance_criteria_clarity`.

**Conditionally:** pick 0-3 extras:

```bash
python3 <SCRIPT> rubrics list-extras --phase issue
```

Picking heuristics:

- Issue body suggests scope concerns (multiple components, "and
  also" patterns, conjunctive title) → `issue_sizing`
- Issue describes a code change in a non-trivial repo without
  pointing at specific files / modules / conventions →
  `context_completeness`
- Repo has multiple in-flight issues that share interfaces / data
  models → `prerequisite_mapping`

### 5. Run each selected reviewer

For each reviewer:

```bash
python3 <SCRIPT> rubrics read --phase issue --slug <slug>
```

Apply the rubric to the issue. Score, verdict, findings.

Notes specific to issue-phase reviewers:

- **devils_advocate_issue** asks the structural questions: smallest
  useful slice? Right abstraction level? Hidden refactor sneaking
  into a feature?
- **spec_fidelity** checks AC ⇄ spec AC mapping. Flag every issue
  AC that doesn't trace to a spec AC.
- **acceptance_criteria_clarity** is the most concrete of the three.
  Imagine reading just the AC text — would two reviewers reach the
  same verdict? If not, fuzzy.

### 6. Aggregate + post a single comment to the issue

Format the entire review as a single GitHub comment with summary
table and per-reviewer details. **Don't post multiple comments** —
one consolidated comment is better for issue-page readability.

Comment template:

```markdown
## Issue review — <date> UTC

| Reviewer | Score | Verdict | Headline |
|---|---|---|---|
| devils_advocate_issue | 8.0 | PROCEED | well-scoped; one minor scope smell |
| spec_fidelity | 9.0 | PROCEED | clean descent from spec X |
| acceptance_criteria_clarity | 7.5 | REVISE | AC #2 lacks methodology |
| issue_sizing (extra) | 8.5 | PROCEED | one PR; balanced ACs |

## Required changes

- **acceptance_criteria_clarity (REVISE):** AC #2 says "p99 < 200ms" —
  needs methodology: under what load? from where? on what hardware?

## Optional improvements

- **devils_advocate_issue (PROCEED-with-nit):** consider whether the
  refactor of `helper.dart` could be extracted to a separate issue
  if it grows.

---

🤖 *Posted by `/issue-review` — see [blueprint-reviewer plugin](https://github.com/infiquetra/infiquetra-claude-plugins/tree/main/plugins/blueprint-reviewer) for rubric details.*
```

Post via:

```bash
gh issue comment <owner>/<repo>#<num> --body-file /tmp/review-comment.md
```

### 7. Surface to the user

After posting:

- Print the comment URL
- List action items (REVISE/BLOCK findings)
- Suggest next step: "If satisfied, move to Ready. Otherwise, address
  the REVISE items above."

## Important: human-in-the-loop, advisory only

Issue review is **advisory**:

- **Do NOT** move the issue to Ready automatically.
- **Do NOT** apply suggested changes.
- **Do NOT** add labels (unless explicitly asked).

Findings are posted; the human decides whether to address them and
when to promote the issue to Ready.

## Targeted invocations

```
/issue-review owner/repo#42 --reviewers spec_fidelity,acceptance_criteria_clarity
/issue-review owner/repo#42 --cores-only
/issue-review owner/repo#42 --dry-run        # surface findings, don't post
/issue-review owner/repo#42 --no-post        # print findings, don't post comment
```

## Difference from automated PR-driven review

This skill is the **manual** path — invoked by the user directly.

The **automated** path (Phase C, future) will trigger when an issue
moves to the **Backlog** column on the Olympus project board, run
the same rubrics, and post the same comment. The skill and the
orchestrator share the rubric library so findings are consistent.

If the user asks "what's the difference between running this manually
vs. auto?", the answer is: **timing and scope of conditionals**.
The auto path runs only the cores plus a deterministic set of
extras based on issue labels; the manual path lets you pick any
extras you want.

## Score-band notes (issue phase calibration)

Issues are concrete enough to expect tighter scores than specs:

- **9.0+** is the bar for "ready to pick up." Issues at this level
  rarely produce R2/R3 review loops.
- **8.0–8.9** is workable but the agent may have to make judgment
  calls during planning.
- **<7.5** likely produces planning round-trips.
- **<6.0** suggests the issue should not be picked up — kick back
  to the author for sharpening.

These are advisory anchors; you (the human) decide whether to act.
