---
title: Orchestrate clean leaves empty lane workspaces behind and cannot release a worktree at merge time
repo: infiquetra-claude-plugins
type: enhancement
team: asgard
project: operations
status: Shaping
labels: enhancement, needs-plan
risk: medium
mode: execute
handoff_maturity: requirements-ready
---

# Orchestrate `clean` leaves empty lane workspaces behind and cannot release a worktree at merge time

### Objective

Let a run clean up after itself completely: retire the herdr workspaces it created, and release a
unit's worktree at the moment its branch becomes deletable.

### Intent

Two related gaps in the cleanup lifecycle, both observed on the completed issue-847 run.

**Empty lane workspaces survive.** `cmd_clean` closes tabs and removes worktrees. It never retires
the workspace. Its own docstring even names the problem it is trying to avoid — "workspace ends up
with a dozen idle tabs nobody can tell apart" — but it stops at the tabs. After the issue-847 run
closed, **seven** lane workspaces (`847-lane-guards`, `-stability`, `-orchestrate`,
`-mission-control`, `-saga`, `-plan`, `-review`) remained as empty shells and had to be retired by
hand with `herdr workspace close`. A workspace list that accumulates dead lanes from every past run
is exactly the indistinguishable clutter the docstring warns about, one level up.

**A worktree blocks its own branch deletion, at merge time.** Issue 844 taught Orchestrate to delete
merged *remote* branches. It did not address the ordering problem that motivated it: GitHub cannot
delete a branch a local worktree still holds. During the issue-847 campaign
`gh pr merge --delete-branch` failed for this reason **three separate times** — on pull requests
867, 869, and 872 — each time reporting:

```
failed to delete local branch <branch>: ... cannot delete branch '<branch>'
used by worktree at '<path>'
```

The third failure was on the pull request that *fixed issue 844*, which is a fair measure of how
easy it is to hit. Each time the coordinator had to remove the worktree by hand, then delete the
local and remote branch separately and read back. `clean --branches` handles this correctly at
run end; there is simply nothing to call at merge time, when the branch actually becomes deletable.

### Out-of-scope / non-goals

- Do not retire a workspace that still holds a live agent, a tab the run does not own, or any
  workspace not created by this run.
- Do not delete a branch or worktree with uncommitted or unpushed work.
- Do not change merged-pull-request proof or ancestry proof from issue 844.
- Do not make ordinary `clean` destructive to remotes; keep remote deletion behind `--branches`.
- Do not take over merging; the coordinator still owns that.

### Files expected to change

- `plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py`
- `plugins/orchestrate/skills/orchestrate/SKILL.md`
- `tests/test_orchestrate_land_clean.py`
- Orchestrate release surfaces required by repository policy

### Tests to add or update

- Retire a run-created workspace once its last tab is closed; read back that it is gone.
- Refuse to retire a workspace that still holds a live agent, and say which one.
- Refuse to retire a workspace the run did not create, even if it is empty.
- Release a single unit's worktree on request, then prove the branch is deletable and delete it.
- Refuse release when the unit worktree is dirty or holds unpushed commits, naming what is at risk.
- Prove repeated cleanup is idempotent and reports already-absent workspaces and worktrees cleanly.
- Mutation-prove each guard: removing it must fail the corresponding refusal test.

### Context library links

- Current implementation: `plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py::cmd_clean`
- The remote-deletion capability this builds on: issue 844
- Real incidents: pull requests 867, 869, and 872, each failing `--delete-branch` on a held worktree
- Workspace residue: issue 847 closeout, seven lane workspaces retired by hand
- Archived run record naming the workspaces: `.orchestrate/run-orch-2026-08-26-847-FINAL.json`

### Verification

```bash
uv run pytest tests/test_orchestrate_land_clean.py -q
uv run ruff check plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py tests/test_orchestrate_land_clean.py
GATE_LOG_DIR=/tmp/gate-run bash scripts/gate.sh > /tmp/gate.log 2>&1
cat /tmp/gate-run/result.txt
```

### Acceptance criteria

- [ ] `clean` retires workspaces the run created, once they hold no live agent and no foreign tab.
- [ ] It refuses to retire any workspace it does not own or that is still occupied, with a reason.
- [ ] A unit's worktree can be released at merge time so its branch becomes deletable.
- [ ] Release refuses on dirty or unpushed state, naming what would be lost.
- [ ] Cleanup is idempotent and reports already-absent resources cleanly.
- [ ] `bash scripts/gate.sh` exits 0 with Orchestrate release surfaces aligned.

### Notes / conventions

Workspace ownership must come from the run record rather than from a name pattern; a prefix match
would eventually retire someone else's workspace. The issue-847 run recorded each unit's
`workspace`, which is the natural ownership key.

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/876
- Number: 876
- Created at: 2026-08-27T00:57:03.912517+00:00

