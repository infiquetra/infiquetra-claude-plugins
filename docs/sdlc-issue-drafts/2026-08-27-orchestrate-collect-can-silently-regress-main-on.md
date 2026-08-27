---
title: Orchestrate collect can silently regress main on a run that integrates by per-unit pull request
repo: infiquetra-claude-plugins
type: defect
team: asgard
project: operations
status: Shaping
labels: defect, needs-plan
risk: high
mode: execute
handoff_maturity: requirements-ready
---

# Orchestrate `collect` can silently regress `main` on a run that integrates by per-unit pull request

### Objective

Make `collect` refuse, rather than perform, a merge that would revert content already on the
authoritative branch.

### Intent

`cmd_collect` exists to bring a run branch home after units `land` on it. Its only preconditions are
that a run branch exists, the working tree is clean, and the run branch is ahead of `HEAD`. It then
runs:

```python
proc = run(["git", "merge", "--no-ff", "--no-edit", r.branch], check=False)
```

Nothing checks whether the run branch's content is still current. That is safe for the
`land`-then-`collect` model it was written for. It is **not** safe for a run that integrates each
unit through its own squash pull request to `main`, which is a model Orchestrate fully supports and
which the issue-847 campaign used for all twenty units.

In that model the run branch never receives the unit work. It holds only the pre-run control
commits — the plan and the document review — frozen at the moment the run started. Meanwhile those
same documents are amended on `main` throughout the run.

**Observed on the completed issue-847 run.** At closeout the run branch `orch/orch-2026-08-26-847`
sat four commits ahead of `main` at `0dc98b5c`, carrying the plan and doc-review as **1,566
insertions across two files**. Both documents had already reached `main` in amended form via commit
`aca6659b`, and the run-branch copies differed from `main`'s by **402 lines** of mid-run amendment.
Running `collect` would have either conflicted or reverted those 402 lines. The coordinator caught
it only by inspecting the diff by hand before running the command, and recorded the skip as a
deliberate deviation in the closeout.

The danger is that `collect` reads as the normal, blessed way to finish a run. An operator following
the documented lifecycle would run it.

### Out-of-scope / non-goals

- Do not remove `collect` or change the `land`-then-`collect` model, which remains correct.
- Do not make `collect` attempt to reconcile or rebase divergent content automatically.
- Do not change `land`, squash-merge integration, or run-branch creation.
- Do not require every run to declare an integration model up front; infer and verify instead.

### Files expected to change

- `plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py`
- `plugins/orchestrate/skills/orchestrate/SKILL.md`
- `tests/test_orchestrate_land_clean.py`
- Orchestrate release surfaces required by repository policy

### Tests to add or update

Against real temporary repositories:

- A `land`-model run where the run branch genuinely carries unit work: `collect` still succeeds.
- A per-unit-pull-request run where the run branch holds only stale control commits whose content is
  already on `main` in **newer** form: `collect` **refuses** and names the files it would revert.
- A run branch whose content is byte-identical to `main`: `collect` reports there is nothing to do,
  and is idempotent.
- A genuine conflict: `collect` still reports the conflict rather than silently resolving it.
- Mutation-prove the guard: removing it must fail the refusal test.

### Context library links

- Current implementation: `plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py::cmd_collect`
- Real incident: issue 847 closeout comment, "Deliberate deviation — `land` and `collect` were not used"
- Archived run record showing the per-unit-pull-request model: `.orchestrate/run-orch-2026-08-26-847-FINAL.json`
- The twenty pull requests that carried that run's work: 849 through 869

### Inputs inventory

- `.orchestrate/run.json` — the active run record: its `branch` (run branch), `base`, and per-unit
  `merge` flags, which together reveal whether units landed on the run branch or went out as
  individual pull requests.
- The run branch ref and the merge target ref (normally `main`), and the diff between them.
- The operator working tree state, already checked today for uncommitted changes.
- Archived run records under `.orchestrate/run-orch-*-FINAL.json`, for reproducing the
  per-unit-pull-request shape in tests.

### Failure modes / pre-mortem

- **Guard too strict.** A legitimate `land`-model `collect` is refused because a unit also touched a
  file that later changed on `main`. Mitigation: refuse only when the merge would replace a target
  version with an older one, not on any overlap; keep the `land`-model test as the guard against
  over-refusal.
- **Guard too loose.** Comparing only the run-branch tip misses stale content further back.
  Mitigation: compare per-path content between merge base, run branch, and target.
- **Ancestry mistaken for currency.** Reaching for `merge-base --is-ancestor` looks right and is
  wrong here: squash-merged content is never an ancestor, so the check passes vacuously and the
  guard silently does nothing. This is the single likeliest way to ship a guard that does not guard.
- **Refusal without a route forward.** An operator who cannot tell what to do next may force the
  merge. Mitigation: the refusal must name the files and state the safe alternative.
- **Conflict masking.** A guard that runs after the merge attempt could leave a dirty tree.
  Mitigation: decide before mutating anything.

### Stop conditions

Stop and report rather than guessing when:

- The run record does not make the integration model determinable, so `collect` cannot tell which
  shape it is in.
- The run branch and the merge target have genuinely diverged in both directions on the same path,
  which is a real merge decision the operator owns.
- Repairing this would require changing `land`, run-branch creation, or squash-merge integration —
  all explicitly out of scope here.
- Any change would make an existing `land`-model run fail to collect.

### Verification

```bash
uv run pytest tests/test_orchestrate_land_clean.py -q
uv run ruff check plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py
GATE_LOG_DIR=/tmp/gate-run bash scripts/gate.sh > /tmp/gate.log 2>&1
cat /tmp/gate-run/result.txt
```

### Acceptance criteria

- [ ] `collect` refuses when merging the run branch would revert content already on the merge target.
- [ ] The refusal names the specific files and states why, rather than failing generically.
- [ ] The `land`-then-`collect` path is unchanged and still succeeds.
- [ ] A no-op `collect` remains a clean no-op.
- [ ] New coverage fails if the guard is removed.
- [ ] `bash scripts/gate.sh` exits 0 with Orchestrate release surfaces aligned.

### Notes / conventions

The cheapest sound guard is a content comparison rather than an ancestry one: for each path the
merge would change, refuse if the merge target already holds a **newer** version. Ancestry alone is
insufficient here, because squash-merged content is never an ancestor.

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/875
- Number: 875
- Created at: 2026-08-27T00:56:07.677267+00:00

