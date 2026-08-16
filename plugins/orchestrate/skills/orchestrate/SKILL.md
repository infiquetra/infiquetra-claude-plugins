---
name: orchestrate
description: Spread one piece of work across several herdr agent sessions — plan it with the operator, run each unit in its own git worktree with any configured agent and any saga capability, then merge the results back. Triggers on "/orchestrate", "orchestrate this", "split this across agents", "run these issues in parallel", "fan this out to multiple sessions", "orchestrate across vendors".
---

# orchestrate

Take one piece of work — a prompt, an issue, a parent issue's children, or a document — decide with
the operator how to split it, and run the pieces across herdr agent sessions.

Each unit gets its own git worktree and branch, so sessions cannot overwrite each other. Each unit
can invoke any saga capability (`/plan`, `/brainstorm`, `/doc-review`, `/work`, `/code-review`,
`/qa`, `/investigate`, …) or just take a plain prompt. Any agent configured on this machine can run
any unit.

## How to use it

Run `/orchestrate <input>`. The command file
(`plugins/orchestrate/commands/orchestrate.md`) carries the full procedure: read the input,
interview the operator, hand over a table for approval, then dispatch.

**Nothing launches until the operator approves the table.**

## The mechanical half

`skills/orchestrate/scripts/orchestrate.py` does the moving parts:

```bash
S=plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py
uv run python $S start --plan .orchestrate/plan.json   # record the run
uv run python $S go                                    # launch every eligible unit
uv run python $S status                                # the table, with live herdr state
uv run python $S settle                                # idle sessions become done
uv run python $S collect                               # merge each finished unit's branch
uv run python $S clean --branches                      # close tabs, remove worktrees
```

`go` launches only units whose `after` dependencies are already done, so calling `settle` then `go`
again is what releases the next wave.

**A unit with dependencies branches from the last one it names**, at launch time rather than up
front — so a `/work` unit opens on top of its `/plan` unit's actual output.

## State

One file, `.orchestrate/run.json`: run id, source, base commit, and per unit its name, vendor,
model, effort, task, dependencies, worktree, branch, tab, herdr agent name, and status. If it is
wrong, delete it — `herdr agent list` is the real truth.

The unit's `name` is the dependency key and never changes. The wrapper uniquifies agent names, so
what herdr calls the session is recorded separately as `agent_name`.

## Agents

Whatever `agent --crews` reports on this machine. Model and effort flags are per vendor:

| Agent | model | effort |
|---|---|---|
| claude | `--model` | — |
| codex | `--model` | `-c model_reasoning_effort=` |
| grok | `-m` | `--reasoning-effort` |
| qwen | `-m` | — |
| opencode | `-m` | — |

An agent not listed launches with no model flags. **qwen does not report interactive readiness**, so
`herdr agent prompt` refuses it; the script falls back to typing into its pane, which is what an
operator would do by hand.

## What this deliberately does not do

It does not verify that a session "really" finished, count tokens, enforce a spend ceiling, reserve
concurrency slots, run a voting panel, or keep a durable register with locks. If a unit went wrong,
you have its worktree, its branch, and its tab — look at them.

An earlier implementation did all of those things, in 14,875 lines of production code and about
15,700 lines of tests. It is preserved on `origin` at `archive/orchestrate-full-implementation` if a
real failure ever justifies pulling a piece of it back.
