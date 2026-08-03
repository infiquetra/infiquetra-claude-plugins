---
title: Coverage report and saga runtime artifacts fall through partial gitignore coverage
repo: infiquetra-claude-plugins
type: defect
team: asgard
project: operations
status: Shaping
labels: defect, hermes-task, needs-plan
risk: low
mode: actionable
handoff_maturity: requirements-ready
---

# Coverage report and saga runtime artifacts fall through partial gitignore coverage

### Objective
Close two partial `.gitignore` coverages so machine-local test and workflow artifacts cannot be
swept into a commit by a blanket `git add -A`.

### Intent
Both gaps are partial coverage rather than outright absence, which is why neither was noticed: the
ignore file mentions each area, just not the specific artifact that actually appears.

**Coverage reports.** `.gitignore:30` ignores `.coverage`, the binary data file. It does not ignore
`coverage.xml`, the report `pytest --cov-report=xml` writes. Same tool, two artifacts, one covered.
The repository's own quality-check instructions run coverage, so the untracked 1.4 MB file appears
in `git status` after any normal test run.

**Saga runtime state.** `.saga/` is ignored selectively — five named paths, not the directory:

- `.saga/engine-prefs.json` (line 63)
- `.saga/engine-overlay.json` (line 65)
- `.saga/adjustment-envelope.json` (line 68)
- `.saga/undo-ledger.jsonl` (line 69)
- `.saga/gates/` (line 70)

(`.saga-worktrees/` at line 61 is a sibling directory, not part of `.saga/`.)

Everything else the saga runtime writes there falls through: `workflow-lease-*.json`,
`workflow-evidence-*/` directories, lease-keeper and renew-loop logs, per-issue invocation-id
pointers, and per-run `.env` files. On this machine that is 61 entries showing as untracked.

The consequence is that `git status` is never clean on a machine that has run a workflow, which
trains the eye to ignore the untracked section — and a blanket `git add -A` would commit workflow
lease and evidence artifacts that are explicitly machine-local.

### Out-of-scope / non-goals
- Do not ignore `.saga/` wholesale if any path under it is intended to be tracked. Establish which,
  if any, are tracked today before choosing between a directory ignore and a broadened pattern.
- Do not delete anything currently on disk under `.saga/`; it holds live lease and evidence records.
- Do not change what the saga runtime writes or where.

### Files expected to change
- `.gitignore`

### Tests to add or update
- No unit test is natural for an ignore file. Verify by command instead (see Verification), and
  state the before/after `git status --short` output in the pull request body.

### Context library links
- `docs/work-sessions/2026-08-03-verify-panel-severity-axis.md`
- `CLAUDE.md` (the quality-check block that runs coverage)

### Acceptance criteria
- [ ] `git check-ignore -q coverage.xml` exits 0.
- [ ] `git check-ignore -q .saga/workflow-lease-example.json` exits 0.
- [ ] `git status --short` on a tree that has run both the test suite and a workflow shows no untracked
   entries from either.
- [ ] `git ls-files .saga/ coverage.xml` returns nothing, confirming nothing currently tracked was
   newly ignored.
- [ ] `uv run python -m pytest -q` exits 0 — the ignore change must not affect collection.

### Verification
```bash
git check-ignore -v coverage.xml
git check-ignore -v .saga/workflow-lease-example.json
git ls-files .saga/ coverage.xml
git status --short
uv run python -m pytest -q
```

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: /private/tmp/claude-501/-Users-jefcox-workspace-infiquetra-infiquetra-claude-plugins/69f09efc-465e-4e84-9258-fcca4901722b/scratchpad/cards/05-gitignore-partial-coverage.md
- Source type: local-file
- Source title: 05-gitignore-partial-coverage

### Recommended Tier Band
opus/high

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/695
- Number: 695
- Created at: 2026-08-03T19:55:12.717536+00:00

