---
title: Saga: the run record and the admission questionnaire
repo: infiquetra-claude-plugins
type: capability
team: asgard
project: operations
status: Ready for Planning
stage: Shaping
labels: capability, needs-plan
risk: medium
mode: execute
handoff_maturity: requirements-ready
---

# Saga: the run record and the admission questionnaire

### Objective

One JSON run record per issue, stored outside any worktree in the primary checkout's saga store and referenced by absolute path, holding the admission answers, the thirteen sdlc run-configuration parameters, the roster with pane identifiers, the units with worktree, branch, and merge-turn state, review results by cycle, and `next_step`. An admission step (`saga admit <issue>`, also the first thing `/plan issue` does) that runs the card validator, fills every defaultable parameter from a per-repository profile and the staffing component, and asks the operator only for the rest in one message: Risk tier and justification, the seven approval-boundary scopes, the destination, staffing overrides, the lens declaration (four always on, conditional lenses proposed), repair allowances, the response to unfinished functional testing, whether the repository has a branch preview, whether `main` is consumed directly, and code, docs, or mixed.

### Intent

The sdlc already enumerates the up-front questions (card contract, Risk, approval boundaries, six issue-review checks, thirteen parameters); nothing implements them, and saga keeps state in ledgers, envelopes, and receipts instead of one record. The record replaces the run-fact, evidence-custody, dispatch-settlement, and effort ledgers, the envelope tokens, and the ship receipts (SR R1, R2). Card 886's fifth finding (a worktree cannot see the primary checkout's git-ignored store) is why the record lives outside worktrees; cards 975 and 989 (unknown record version, unknown fields) are acceptance criteria here.

### Out-of-scope / non-goals

- No board write (A11 submits moves through mission-control).
- No roster creation (A6).
- No second store: the spore hooks freeze and re-inject this record and nothing else.

### Files expected to change

- `plugins/saga/scripts/run_record.py` (new), `plugins/saga/scripts/admission.py` (new)
- `plugins/saga/skills/plan/SKILL.md` (admission at the start of `/plan issue`)
- `plugins/saga/hooks/precompact_spore_hook.py`, `compact_spore_session_hook.py` (read the record)
- `plugins/saga/scripts/saga.py` (state engine reads and writes the record)
- `plugins/saga/references/run-record.md` (new; the schema), `plugins/saga/references/repository-profile.md` (new)
- release surfaces

### Tests to add or update

- `tests/test_run_record.py`: round-trips unknown top-level fields; an unknown record version yields a one-line refusal and exit 3, never a traceback; the record path is absolute and outside any worktree; `next_step` survives freeze and re-inject.
- `tests/test_admission.py`: a card failing the validator stops with the missing fields named; every defaultable parameter is filled without a question; the operator is asked exactly once for the non-defaultable set; answers persist and are not re-asked.

### Context library links

- coding_standards: _none_

General references:
- SDLC/docs/lifecycle/run-model.md (the thirteen parameters, lines 129 to 156); SDLC/docs/process/human-intent-intake.md; SDLC/docs/process/card-schema.md; SR section 5 and R1, R2; TR R5, R18

### Acceptance criteria

- [ ] `uv run python plugins/saga/scripts/admission.py --issue <N> --dry-run` prints the questions it would ask and the defaults it filled, and asks nothing already answered in the record.
- [ ] `uv run python plugins/saga/scripts/run_record.py show <issue>` prints the record with `next_step`, and `run_record.py show` on a record with an unknown version exits 3 with one line.
- [ ] A worktree created by `git worktree add /tmp/wt` can read the record by the absolute path the admission step printed.
- [ ] `uv run pytest tests/test_run_record.py tests/test_admission.py -q` passes.

### Verification

```bash
uv run python plugins/saga/scripts/admission.py --issue <N> --dry-run
uv run python plugins/saga/scripts/run_record.py show <N>
uv run pytest tests/test_run_record.py tests/test_admission.py -q
```

### Risk

medium

every other child reads this record; a schema mistake ripples, so the schema is a reference document with a round-trip test before any consumer lands.

### Handoff maturity
requirements-ready

### Recommended Tier Band
opus/high

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/1023
- Number: 1023
- Created at: 2026-09-19T14:43:50.157555+00:00

