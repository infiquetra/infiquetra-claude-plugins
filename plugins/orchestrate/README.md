# orchestrate

Orchestrate spreads one piece of work across tracked [Herdr](https://github.com/infiquetra)
agent sessions. Each unit runs on its own Git branch and worktree, while one local run record keeps
the operator's view of dependencies, live sessions, commits, and landing state coherent.

The plugin is deliberately small. It ships two Python modules:

- `skills/orchestrate/scripts/orchestrate.py` is the standard-library command-line interface. It
  validates a plan, creates and launches units, records state, waits for Herdr events, reports drift,
  lands completed branches, and cleans up worktrees and sessions.
- `skills/orchestrate/scripts/herdr_events.py` validates Herdr protocol 19 event messages and holds
  the `events.subscribe` connection used by `wait`. When the event socket is unavailable,
  `orchestrate.py` falls back to bounded per-session waits.

The operator-facing procedure and planning contract live in
`commands/orchestrate.md` and `skills/orchestrate/SKILL.md`. The Python modules execute an approved
plan; they do not invent its split or choose vendors on their own.

## Quick start

Resolve the installed script, then run it from the repository being coordinated:

```bash
S="$CLAUDE_PLUGIN_ROOT/skills/orchestrate/scripts/orchestrate.py"
[ -f "$S" ] || S=$(ls -d ~/.claude/plugins/cache/*/orchestrate/*/skills/orchestrate/scripts/orchestrate.py | sort -V | tail -1)

python3 "$S" roster
python3 "$S" start --plan .orchestrate/plan.json
python3 "$S" go
python3 "$S" wait
python3 "$S" settle
python3 "$S" status
python3 "$S" land
python3 "$S" check
python3 "$S" collect
python3 "$S" clean --merged --branches
```

The command uses only Python's standard library, so the driven repository does not need a Python
environment. `roster` reads the local `agents` wrapper at invocation time instead of relying on a
stored vendor list.

## State and task files

The run record is `.orchestrate/run.json`. Long task text and hand-authored briefs belong under
`.orchestrate/tasks/`; do not point a unit at a session scratchpad or temporary directory that can
disappear before the unit reads it. `start` adds `.orchestrate/` once to the driven repository's
local `.git/info/exclude`, preserving existing rules, so run state does not appear as untracked work
and is never committed merely to keep the working tree clean.

Each unit records its stable name, requested vendor and tier, task, ordering edges, worktree, branch,
Herdr identifiers, status, and notes. Git and Herdr remain the source of truth: `status` computes the
current commit count and landed state, while `check` compares the record with both systems and
reports branches, sessions, or commits the record no longer describes.

## Execution model

`start` creates one run branch. `go` creates a branch and worktree for each eligible unit, launches
the selected agent there, and delivers the task only after the session is ready. The two ordering
edges gate launch in the same way but carry different meaning:

- `after` means the unit needs another unit's output.
- `serialize` means the units must not overlap, without claiming an output dependency.

`land` merges completed unit branches into the run branch through a detached throwaway worktree. A
merge conflict retains and names that worktree for recovery. `collect` is the separate, final merge
from the run branch into the operator's current tree and therefore still requires that tree to be
clean.

`wait` uses `herdr_events.py` to wake on session changes, then confirms idle observations before a
unit can settle. A single idle observation is only a gap between turns. `status` and `check` surface
delivery warnings and units that committed nothing instead of silently treating an idle session as
successful work.

## Boundaries

Orchestrate coordinates sessions; it does not prove that a child followed its instructions, impose a
spend ceiling, reserve host-wide capacity, or run a private review-consensus policy. A unit's branch,
worktree, Herdr session, commit history, and task files are retained when the command cannot safely
show that the work landed.
