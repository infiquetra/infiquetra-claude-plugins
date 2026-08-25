---
title: [DEFECT] Mission Control prepared-issue revision can leave a draft with duplicated front matter and body
repo: infiquetra-claude-plugins
type: defect
team: asgard
project: operations
status: Shaping
labels: defect, needs-plan
risk: medium
handoff_maturity: requirements-ready
---

# [DEFECT] Mission Control prepared-issue revision can leave a draft with duplicated front matter and body

### Objective

A stored prepared-issue draft must always be a single well-formed document — exactly one
front-matter block and one body — after any number of revisions; today at least one revised draft
on disk is doubled.

## Observed behavior

The final prepared draft for issue #770,
`docs/sdlc-issue-drafts/2026-08-23-negative-delta-seconds-retry-after-yields-a-nega-3.md`, is
malformed on disk: two `---`-delimited YAML front-matter blocks back to back (four `---` fences
total — re-verified 2026-08-24 by direct read: blocks at lines 1-12 and 16-26) and the entire card
body twice, once under `##` headings and again under `###` headings (lines 28-188). This suggests
the prepare/revise path appended the revised document instead of replacing prior content. The
pipeline still succeeded: the sidecar JSON records `readiness.passed: true` and
`created_issue_number: 770`, and the created GitHub issue body is clean — the corruption is in the
stored draft artifact only, as far as observed.

Provenance limitation, stated plainly: no transcript of the command that wrote this file was found
in the audit window, so append-instead-of-replace is inferred from the artifact, not observed live.
Filed on the artifact evidence per operator triage; root-cause confirmation belongs to
implementation.

## Operator impact

Cosmetic today, but the stored draft is the reviewable artifact of record for prepared handoffs — a
doubled draft misrepresents what was approved, breaks any future re-read/re-validate of the draft,
and erodes trust in the prepare → revise → create-prepared chain.

## Evidence and provenance

- `docs/sdlc-issue-drafts/2026-08-23-negative-delta-seconds-retry-after-yields-a-nega-3.md`
  (lines 1-26: two front-matter blocks; 28-188: doubled body). Sidecar `…-nega-3.json`:
  `readiness.passed: true`, `created_issue_number: 770`, created 2026-08-23T02:42:50Z, updated
  02:43:04Z.
- Sibling drafts `…-nega.md` (02:41:29Z) and `…-nega-2.md` (02:41:55Z) are well-formed
  single-document drafts — only the final revised draft is doubled.
- Transcript-audit report: `/private/tmp/plugin-transcript-audit-20260823/FINAL-REPORT.md`,
  needs-investigation N1 (lane4), accepted by operator triage 2026-08-24.

### Intent

Root-cause the draft write/rewrite path in `sdlc_manager.py`, guarantee replacement semantics for
revisions, add a regression test asserting single-document shape after revision, and make the
readiness validator flag a multi-fence draft loudly if the shape ever recurs.

### Out-of-scope / non-goals

- The GitHub issue body composition (observed clean).
- card_validator scoring rules beyond the new multi-fence shape check.
- The #770 fleet-core defect itself.

### Files expected to change

- `plugins/mission-control/scripts/sdlc_manager.py`
- `tests/test_sdlc_draft_revision.py` (new; or extension of the existing sdlc_manager test module)
- `plugins/mission-control/.claude-plugin/plugin.json`, `plugins/mission-control/CHANGELOG.md`,
  `.claude-plugin/marketplace.json` (release-surface parity)

### Tests to add or update

- `tests/test_sdlc_draft_revision.py` (new): prepare a draft in a tmp path, revise it twice, assert
  the stored file contains exactly two `---` fences and one body; plus a validator test asserting a
  deliberately doubled draft is flagged as a blocking gap, not passed.

### Context library links

- source_context: `/private/tmp/plugin-transcript-audit-20260823/issue-sources/7-mission-control-draft-revision.md`
  (audit task dir — ephemeral; the durable specimen is the `…-nega-3.md` file in-repo)

### Acceptance criteria

- [ ] `uv run pytest tests/test_sdlc_draft_revision.py -q` passes — revise-twice yields a
      single-document draft (`grep -c '^---$' <draft>` = `2` asserted in the test).
- [ ] The revision path is shown (test or trace in the PR) to replace draft content rather than
      append.
- [ ] Readiness evaluation of a deliberately doubled draft reports a blocking gap naming the
      multi-fence shape — asserted in the validator test.

### Verification

```bash
uv run pytest tests/test_sdlc_draft_revision.py -q
grep -c '^---$' docs/sdlc-issue-drafts/2026-08-23-negative-delta-seconds-retry-after-yields-a-nega-3.md  # reference specimen: currently 4
scripts/gate.sh
```

Validation belongs in implementation — no fresh reproduction was required to file (operator
instruction, 2026-08-24). The on-disk `…-nega-3.md` artifact is the reference specimen.

### Handoff maturity

requirements-ready

### Suggested next action

Use `/plan <issue>` to create an implementation plan.

### Recommended Tier Band

sonnet/high

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/785
- Number: 785
- Created at: 2026-08-24T03:59:24.674368+00:00

